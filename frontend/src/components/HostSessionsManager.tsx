import { useEffect, useState } from "react";
import { useAuthStore } from "../stores/authStore";
import { useGameStore } from "../stores/gameStore";
import { useSocketStore } from "../stores/socketStore";
import { useChatStore } from "../stores/chatStore";

interface HostSessionItem {
  id: number;
  title: string;
  is_active: boolean;
  created_at: string;
  participant_count: number;
}

export default function HostSessionsManager() {
  const userId = useAuthStore((s) => s.userId);
  const currentCharacter = useGameStore((s) => s.currentCharacter);
  const setSession = useGameStore((s) => s.setSession);
  const clearNotifications = useGameStore((s) => s.clearNotifications);
  const connected = useSocketStore((s) => s.connected);
  const joinSessionSock = useSocketStore((s) => s.joinSession);
  const clearChat = useChatStore((s) => s.clear);
  const [items, setItems] = useState<HostSessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    if (!userId) return;
    try {
      setError(null);
      if (!loading) setRefreshing(true);
      const res = await fetch(`http://localhost:8000/api/sessions/host/${userId}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setItems(data);
    } catch (e: any) {
      setError(e?.message || "Failed to load host sessions");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    load();
  }, [userId]);

  const restart = async (id: number) => {
    if (!userId) return;
    if (!currentCharacter) {
      setError("Select a character first to restart and join.");
      return;
    }
    try {
      const res = await fetch(
        `http://localhost:8000/api/sessions/${id}/restart?user_id=${userId}`,
        { method: "POST" }
      );
      if (!res.ok) throw new Error(await res.text());
      // Ensure participant record and socket join
      await fetch(`http://localhost:8000/api/sessions/${id}/join`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, character_id: currentCharacter.id }),
      });

      // Set store to navigate into session
      const it = items.find((x) => x.id === id);
      if (it) {
        clearChat();
        clearNotifications();
        setSession({ id: it.id, title: it.title, hostUserId: userId });
      }

      if (connected) {
        joinSessionSock(id, userId, currentCharacter.id);
      }

      await load();
    } catch (e) {
      console.error(e);
      setError("Failed to restart session");
    }
  };

  const endSession = async (id: number) => {
    if (!userId) return;
    try {
      const res = await fetch(
        `http://localhost:8000/api/sessions/${id}/end?user_id=${userId}`,
        { method: "POST" }
      );
      if (!res.ok) throw new Error(await res.text());
      await load();
    } catch (e) {
      console.error(e);
      setError("Failed to end session");
    }
  };

  const del = async (id: number) => {
    if (!userId) return;
    if (!confirm("Delete this session permanently?")) return;
    try {
      const res = await fetch(`http://localhost:8000/api/sessions/${id}?user_id=${userId}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(await res.text());
      await load();
    } catch (e) {
      console.error(e);
      setError("Failed to delete session (make sure it is ended)");
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-card hover:shadow-card-hover transition-all duration-300 h-full flex flex-col">
      <div className="mb-6 pb-4 border-b border-slate-100">
        <h3 className="text-xl font-bold text-slate-800 flex items-center gap-2">
          <span className="text-2xl">🗂️</span> 내 세션
        </h3>
        <p className="text-slate-500 text-sm mt-1">저장된 세션을 관리하세요</p>
        <div className="mt-3">
          <button
            onClick={load}
            disabled={loading || refreshing}
            className="inline-flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 px-3 py-1.5 rounded-lg text-xs font-semibold shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {refreshing ? (
              <>
                <span className="w-3 h-3 border-2 border-slate-300 border-t-slate-700 rounded-full animate-spin" />
                새로고침 중...
              </>
            ) : (
              <>새로고침</>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-100 text-red-700 px-4 py-3 rounded-lg text-sm mb-4">
          {error}
        </div>
      )}

      <div className="space-y-2 overflow-y-auto" style={{ maxHeight: "400px" }}>
        {loading ? (
          <div className="text-center py-8 text-slate-400">로딩 중...</div>
        ) : items.length === 0 ? (
          <div className="text-center py-8 text-slate-400">저장된 세션이 없습니다</div>
        ) : (
          items.map((s) => (
            <div key={s.id} className="bg-slate-50 border border-slate-200 rounded-lg p-4">
              <div className="flex flex-col gap-3">
                {/* Title at top */}
                <div>
                  <h5 className="font-semibold text-slate-800">{s.title}</h5>
                </div>
                
                {/* Status badge right below title */}
                <div>
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${
                      s.is_active ? "bg-green-100 text-green-700" : "bg-slate-200 text-slate-700"
                    }`}
                  >
                    {s.is_active ? "활성" : "종료됨"}
                  </span>
                </div>
                
                {/* Session info */}
                <div className="text-xs text-slate-500">
                  {`Session #${s.id} • ${new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(s.created_at))} • ${s.participant_count} players`}
                </div>
                
                {/* Buttons at bottom */}
                <div className="flex items-center gap-2">
                  {s.is_active ? (
                    <button
                      onClick={() => endSession(s.id)}
                      className="bg-yellow-600 hover:bg-yellow-700 text-white px-3 py-1.5 rounded text-xs font-semibold"
                      title="세션 종료 (플레이어 연결 해제됨)"
                    >
                      종료
                    </button>
                  ) : (
                    <button
                      onClick={() => restart(s.id)}
                      className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded text-xs font-semibold"
                    >
                      재시작
                    </button>
                  )}
                  <button
                    onClick={() => del(s.id)}
                    className={`px-3 py-1.5 rounded text-xs font-semibold border ${
                      s.is_active
                        ? "bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed"
                        : "bg-white hover:bg-red-50 text-red-600 border-red-200"
                    }`}
                    disabled={s.is_active}
                    title={s.is_active ? "세션을 먼저 종료하세요" : "영구 삭제"}
                  >
                    삭제
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}