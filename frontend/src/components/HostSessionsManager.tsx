import { useCallback, useEffect, useRef, useState } from "react";
import { useAuthStore } from "../stores/authStore";
import { useGameStore } from "../stores/gameStore";
import { useSocketStore } from "../stores/socketStore";
import { useChatStore } from "../stores/chatStore";

const API_BASE_URL = import.meta.env.VITE_API_URL || "";
const KST_FORMATTER = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

interface HostSessionItem {
  id: number;
  title: string;
  world_prompt: string;
  system_prompt?: string;
  is_active: boolean;
  created_at: string;
  participant_count: number;
  story_log_count: number;
}

interface SessionDuplicateResponse {
  session_id: number;
  message: string;
}

interface JudgmentDetail {
  id: number;
  character_id: number;
  character_name: string;
  action_text: string;
  action_type: string | null;
  dice_result: number | null;
  modifier: number;
  final_value: number | null;
  difficulty: number;
  outcome: string | null;
}

interface StoryLogEntry {
  id: number;
  role: "USER" | "AI";
  content: string;
  created_at: string;
  judgments?: JudgmentDetail[] | null;
}

interface StoryLogsResponse {
  session_id: number;
  logs: StoryLogEntry[];
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
  const [busySessionId, setBusySessionId] = useState<number | null>(null);
  const [busyStoryLogId, setBusyStoryLogId] = useState<number | null>(null);
  const [busyJudgmentId, setBusyJudgmentId] = useState<number | null>(null);
  const [storyActionLoading, setStoryActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editWorldPrompt, setEditWorldPrompt] = useState("");

  const [storySessionId, setStorySessionId] = useState<number | null>(null);
  const [storyLoading, setStoryLoading] = useState(false);
  const [storyEntries, setStoryEntries] = useState<StoryLogEntry[]>([]);
  const [editingStoryLogId, setEditingStoryLogId] = useState<number | null>(null);
  const [storyEditRole, setStoryEditRole] = useState<"USER" | "AI">("AI");
  const [storyEditContent, setStoryEditContent] = useState("");
  const [newStoryRole, setNewStoryRole] = useState<"USER" | "AI">("AI");
  const [newStoryContent, setNewStoryContent] = useState("");
  const hasLoadedOnceRef = useRef(false);
  const [expandedJudgments, setExpandedJudgments] = useState<Set<number>>(new Set());

  const toggleJudgmentExpand = (entryId: number) => {
    setExpandedJudgments((prev) => {
      const next = new Set(prev);
      if (next.has(entryId)) next.delete(entryId);
      else next.add(entryId);
      return next;
    });
  };

  const outcomeColor = (outcome: string | null) => {
    if (!outcome) return "text-slate-500";
    if (outcome === "대성공") return "text-emerald-600 font-bold";
    if (outcome === "성공") return "text-emerald-600";
    if (outcome === "실패") return "text-red-600";
    if (outcome === "대실패") return "text-red-600 font-bold";
    return "text-slate-600";
  };

  const getSystemPrompt = (session: HostSessionItem) => session.system_prompt ?? session.world_prompt;
  const patchSessionItem = (id: number, patch: Partial<HostSessionItem>) => {
    setItems((prev) => prev.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  };
  const removeSessionItem = (id: number) => {
    setItems((prev) => prev.filter((item) => item.id !== id));
  };

  const parseError = useCallback(async (res: Response) => {
    const text = await res.text();
    if (!text) return `Request failed (${res.status})`;
    try {
      const parsed = JSON.parse(text);
      if (typeof parsed?.detail === "string") return parsed.detail;
      return text;
    } catch {
      return text;
    }
  }, []);

  const load = useCallback(async () => {
    if (!userId) return;
    try {
      setError(null);
      if (hasLoadedOnceRef.current) setRefreshing(true);
      const res = await fetch(`${API_BASE_URL}/api/sessions/host/${userId}`);
      if (!res.ok) throw new Error(await parseError(res));
      const data = (await res.json()) as HostSessionItem[];
      setItems(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load host sessions");
    } finally {
      setLoading(false);
      setRefreshing(false);
      hasLoadedOnceRef.current = true;
    }
  }, [parseError, userId]);

  const loadStoryEntries = useCallback(async (sessionId: number): Promise<number | null> => {
    try {
      setStoryLoading(true);
      setError(null);
      const res = await fetch(`${API_BASE_URL}/api/story_logs/${sessionId}`);
      if (!res.ok) throw new Error(await parseError(res));
      const data = (await res.json()) as StoryLogsResponse;
      const logs = data.logs ?? [];
      setStoryEntries(logs);
      return logs.length;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load story logs");
      return null;
    } finally {
      setStoryLoading(false);
    }
  }, [parseError]);

  useEffect(() => {
    hasLoadedOnceRef.current = false;
    setLoading(true);
    void load();
  }, [load]);

  useEffect(() => {
    if (!storySessionId) return;
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setStorySessionId(null);
        setStoryEntries([]);
        setEditingStoryLogId(null);
        setNewStoryContent("");
      }
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [storySessionId]);

  const restart = async (id: number) => {
    if (!userId) return;
    if (!currentCharacter) {
      setError("Select a character first to restart and join.");
      return;
    }
    try {
      setBusySessionId(id);
      setError(null);
      setNotice(null);
      const res = await fetch(`${API_BASE_URL}/api/sessions/${id}/restart?user_id=${userId}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(await parseError(res));

      const joinRes = await fetch(`${API_BASE_URL}/api/sessions/${id}/join`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, character_id: currentCharacter.id }),
      });
      if (!joinRes.ok) throw new Error(await parseError(joinRes));

      const it = items.find((x) => x.id === id);
      if (it) {
        clearChat();
        clearNotifications();
        setSession({ id: it.id, title: it.title, hostUserId: userId });
      }

      if (connected) {
        joinSessionSock(id, userId, currentCharacter.id);
      }

      patchSessionItem(id, {
        is_active: true,
        participant_count: Math.max(1, it?.participant_count ?? 0),
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to restart session");
    } finally {
      setBusySessionId(null);
    }
  };

  const endSession = async (id: number) => {
    if (!userId) return;
    try {
      setBusySessionId(id);
      setError(null);
      setNotice(null);
      const res = await fetch(`${API_BASE_URL}/api/sessions/${id}/end?user_id=${userId}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(await parseError(res));
      if (editingId === id) setEditingId(null);
      patchSessionItem(id, { is_active: false, participant_count: 0 });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to end session");
    } finally {
      setBusySessionId(null);
    }
  };

  const duplicateSession = async (id: number) => {
    if (!userId) return;
    try {
      setBusySessionId(id);
      setError(null);
      setNotice(null);
      const res = await fetch(`${API_BASE_URL}/api/sessions/${id}/duplicate?user_id=${userId}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(await parseError(res));
      const data = (await res.json()) as SessionDuplicateResponse;
      setNotice(`세션이 복제되었습니다. (새 세션 #${data.session_id})`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to duplicate session");
    } finally {
      setBusySessionId(null);
    }
  };

  const startEdit = (session: HostSessionItem) => {
    setEditingId(session.id);
    setEditTitle(session.title);
    setEditWorldPrompt(getSystemPrompt(session));
    setError(null);
    setNotice(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditTitle("");
    setEditWorldPrompt("");
  };

  const saveEdit = async (id: number) => {
    if (!userId) return;
    const trimmedTitle = editTitle.trim();
    const trimmedPrompt = editWorldPrompt.trim();
    if (!trimmedTitle) {
      setError("세션 제목을 입력하세요.");
      return;
    }
    if (!trimmedPrompt) {
      setError("시스템 프롬프트를 입력하세요.");
      return;
    }

    try {
      setBusySessionId(id);
      setError(null);
      setNotice(null);
      const res = await fetch(`${API_BASE_URL}/api/sessions/${id}?user_id=${userId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: trimmedTitle,
          system_prompt: trimmedPrompt,
        }),
      });
      if (!res.ok) throw new Error(await parseError(res));
      cancelEdit();
      setNotice("세션 정보를 수정했습니다.");
      patchSessionItem(id, {
        title: trimmedTitle,
        world_prompt: trimmedPrompt,
        system_prompt: trimmedPrompt,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update session");
    } finally {
      setBusySessionId(null);
    }
  };

  const del = async (id: number) => {
    if (!userId) return;
    if (!confirm("이 세션을 영구 삭제할까요?")) return;
    try {
      setBusySessionId(id);
      setError(null);
      setNotice(null);
      const res = await fetch(`${API_BASE_URL}/api/sessions/${id}?user_id=${userId}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(await parseError(res));
      if (editingId === id) cancelEdit();
      if (storySessionId === id) {
        closeStoryManager();
      }
      setNotice("세션을 삭제했습니다.");
      removeSessionItem(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete session");
    } finally {
      setBusySessionId(null);
    }
  };

  const closeStoryManager = () => {
    setStorySessionId(null);
    setStoryEntries([]);
    setEditingStoryLogId(null);
    setNewStoryContent("");
  };

  const openStoryManager = async (sessionId: number) => {
    setStorySessionId(sessionId);
    setEditingStoryLogId(null);
    setNewStoryContent("");
    await loadStoryEntries(sessionId);
  };

  const startStoryEdit = (entry: StoryLogEntry) => {
    setEditingStoryLogId(entry.id);
    setStoryEditRole(entry.role);
    setStoryEditContent(entry.content);
    setError(null);
    setNotice(null);
  };

  const cancelStoryEdit = () => {
    setEditingStoryLogId(null);
    setStoryEditRole("AI");
    setStoryEditContent("");
  };

  const saveStoryEdit = async (sessionId: number, logId: number) => {
    if (!userId) return;
    const content = storyEditContent.trim();
    if (!content) {
      setError("메시지 내용을 입력하세요.");
      return;
    }
    try {
      setBusyStoryLogId(logId);
      setError(null);
      setNotice(null);
      const res = await fetch(`${API_BASE_URL}/api/story_logs/entry/${logId}?user_id=${userId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role: storyEditRole,
          content,
        }),
      });
      if (!res.ok) throw new Error(await parseError(res));
      cancelStoryEdit();
      setNotice("스토리 메시지를 수정했습니다.");
      const count = await loadStoryEntries(sessionId);
      if (count !== null) {
        patchSessionItem(sessionId, { story_log_count: count });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update story log");
    } finally {
      setBusyStoryLogId(null);
    }
  };

  const deleteStoryEntry = async (sessionId: number, logId: number) => {
    if (!userId) return;
    if (!confirm("이 메시지를 삭제할까요? 연결된 판정은 스토리 연결이 해제됩니다.")) return;
    try {
      setBusyStoryLogId(logId);
      setError(null);
      setNotice(null);
      const res = await fetch(`${API_BASE_URL}/api/story_logs/entry/${logId}?user_id=${userId}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(await parseError(res));
      if (editingStoryLogId === logId) cancelStoryEdit();
      setNotice("스토리 메시지를 삭제했습니다.");
      const count = await loadStoryEntries(sessionId);
      if (count !== null) {
        patchSessionItem(sessionId, { story_log_count: count });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete story log");
    } finally {
      setBusyStoryLogId(null);
    }
  };

  const deleteJudgmentEntry = async (sessionId: number, judgmentId: number) => {
    if (!userId) return;
    if (!confirm("이 행동 메시지를 삭제할까요?")) return;

    try {
      setBusyJudgmentId(judgmentId);
      setError(null);
      setNotice(null);
      const res = await fetch(`${API_BASE_URL}/api/story_logs/judgment/${judgmentId}?user_id=${userId}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(await parseError(res));

      setNotice("행동 메시지를 삭제했습니다.");
      const count = await loadStoryEntries(sessionId);
      if (count !== null) {
        patchSessionItem(sessionId, { story_log_count: count });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete action message");
    } finally {
      setBusyJudgmentId(null);
    }
  };

  const addStoryEntry = async (sessionId: number) => {
    if (!userId) return;
    const content = newStoryContent.trim();
    if (!content) {
      setError("추가할 메시지를 입력하세요.");
      return;
    }
    try {
      setStoryActionLoading(true);
      setError(null);
      setNotice(null);
      const res = await fetch(`${API_BASE_URL}/api/story_logs/${sessionId}/entries?user_id=${userId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role: newStoryRole,
          content,
        }),
      });
      if (!res.ok) throw new Error(await parseError(res));
      setNewStoryContent("");
      setNotice("스토리 메시지를 추가했습니다.");
      const count = await loadStoryEntries(sessionId);
      if (count !== null) {
        patchSessionItem(sessionId, { story_log_count: count });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create story log");
    } finally {
      setStoryActionLoading(false);
    }
  };

  const storySession = storySessionId ? items.find((item) => item.id === storySessionId) ?? null : null;

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-card hover:shadow-card-hover transition-all duration-300 h-full flex flex-col">
      <div className="mb-6 pb-4 border-b border-slate-100">
        <h3 className="text-xl font-bold text-slate-800 flex items-center gap-2">
          <span className="text-2xl">🗂️</span> 내 세션
        </h3>
        <p className="text-slate-500 text-sm mt-1">종료된 세션을 복제/수정/재시작하고 스토리 메시지를 직접 관리하세요</p>
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
      {notice && (
        <div className="bg-emerald-50 border border-emerald-100 text-emerald-700 px-4 py-3 rounded-lg text-sm mb-4">
          {notice}
        </div>
      )}

      <div className="space-y-2 overflow-y-auto" style={{ maxHeight: "600px" }}>
        {loading ? (
          <div className="text-center py-8 text-slate-400">로딩 중...</div>
        ) : items.length === 0 ? (
          <div className="text-center py-8 text-slate-400">저장된 세션이 없습니다</div>
        ) : (
          items.map((s) => (
            <div key={s.id} className="bg-slate-50 border border-slate-200 rounded-lg p-4">
              <div className="flex flex-col gap-3">
                {editingId === s.id ? (
                  <div className="space-y-2">
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
                      placeholder="세션 제목"
                    />
                    <textarea
                      value={editWorldPrompt}
                      onChange={(e) => setEditWorldPrompt(e.target.value)}
                      rows={4}
                      className="w-full border border-slate-300 rounded px-3 py-2 text-sm resize-y"
                      placeholder="시스템 프롬프트 (가장 처음 적용되는 지시문)"
                    />
                  </div>
                ) : (
                  <div>
                    <h5 className="font-semibold text-slate-800">{s.title}</h5>
                    <p className="text-xs text-slate-500 mt-1 whitespace-pre-wrap break-words line-clamp-2">{getSystemPrompt(s)}</p>
                  </div>
                )}

                <div>
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${
                      s.is_active ? "bg-green-100 text-green-700" : "bg-slate-200 text-slate-700"
                    }`}
                  >
                    {s.is_active ? "활성" : "종료됨"}
                  </span>
                </div>

                <div className="text-xs text-slate-500">
                  {`Session #${s.id} • ${KST_FORMATTER.format(new Date(s.created_at))} • 참가 ${s.participant_count}명 • 스토리 로그 ${s.story_log_count}개`}
                </div>

                <div className="flex items-center flex-wrap gap-2">
                  {editingId === s.id ? (
                    <>
                      <button
                        onClick={() => saveEdit(s.id)}
                        disabled={busySessionId === s.id}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-1.5 rounded text-xs font-semibold disabled:opacity-50"
                      >
                        저장
                      </button>
                      <button
                        onClick={cancelEdit}
                        disabled={busySessionId === s.id}
                        className="bg-white hover:bg-slate-100 text-slate-700 px-3 py-1.5 rounded text-xs font-semibold border border-slate-200 disabled:opacity-50"
                      >
                        취소
                      </button>
                    </>
                  ) : (
                    <>
                      {s.is_active ? (
                        <button
                          onClick={() => endSession(s.id)}
                          disabled={busySessionId === s.id}
                          className="bg-yellow-600 hover:bg-yellow-700 text-white px-3 py-1.5 rounded text-xs font-semibold disabled:opacity-50"
                          title="세션 종료 (플레이어 연결 해제됨)"
                        >
                          종료
                        </button>
                      ) : (
                        <button
                          onClick={() => restart(s.id)}
                          disabled={busySessionId === s.id}
                          className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded text-xs font-semibold disabled:opacity-50"
                        >
                          재시작
                        </button>
                      )}
                      <button
                        onClick={() => startEdit(s)}
                        className={`px-3 py-1.5 rounded text-xs font-semibold border ${
                          s.is_active
                            ? "bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed"
                            : "bg-white hover:bg-slate-100 text-slate-700 border-slate-200"
                        }`}
                        disabled={s.is_active || busySessionId === s.id}
                        title={s.is_active ? "세션을 먼저 종료하세요" : "세션 제목/시스템 프롬프트 수정"}
                      >
                        세션/프롬프트 수정
                      </button>
                      <button
                        onClick={() => duplicateSession(s.id)}
                        className={`px-3 py-1.5 rounded text-xs font-semibold border ${
                          s.is_active
                            ? "bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed"
                            : "bg-white hover:bg-indigo-50 text-indigo-700 border-indigo-200"
                        }`}
                        disabled={s.is_active || busySessionId === s.id}
                        title={s.is_active ? "세션을 먼저 종료하세요" : "현재 세션 복제"}
                      >
                        복제
                      </button>
                      <button
                        onClick={() => openStoryManager(s.id)}
                        className={`px-3 py-1.5 rounded text-xs font-semibold border ${
                          s.is_active
                            ? "bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed"
                            : "bg-white hover:bg-violet-50 text-violet-700 border-violet-200"
                        }`}
                        disabled={s.is_active || busySessionId === s.id}
                        title={s.is_active ? "세션을 먼저 종료하세요" : "스토리 관리 화면 열기"}
                      >
                        스토리 관리
                      </button>
                      <button
                        onClick={() => del(s.id)}
                        className={`px-3 py-1.5 rounded text-xs font-semibold border ${
                          s.is_active
                            ? "bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed"
                            : "bg-white hover:bg-red-50 text-red-600 border-red-200"
                        }`}
                        disabled={s.is_active || busySessionId === s.id}
                        title={s.is_active ? "세션을 먼저 종료하세요" : "영구 삭제"}
                      >
                        삭제
                      </button>
                    </>
                  )}
                </div>

              </div>
            </div>
          ))
        )}
      </div>

      {storySessionId && storySession && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm p-2 sm:p-6">
          <div className="mx-auto flex h-full w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 sm:px-6">
              <div>
                <h4 className="text-base font-bold text-slate-800">스토리 관리</h4>
                <p className="mt-0.5 text-xs text-slate-500">{`Session #${storySession.id} • ${storySession.title}`}</p>
              </div>
              <button
                onClick={closeStoryManager}
                className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                닫기
              </button>
            </div>

            <div className="border-b border-slate-100 bg-slate-50/80 px-4 py-3 sm:px-6">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="text-xs text-slate-500">{`메시지 ${storyEntries.length}개`}</span>
                <button
                  onClick={() => loadStoryEntries(storySession.id)}
                  disabled={storyLoading}
                  className="rounded border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  {storyLoading ? "로딩..." : "다시 불러오기"}
                </button>
              </div>

              <div className="rounded-lg border border-slate-200 bg-white p-3">
                <p className="mb-2 text-xs font-semibold text-slate-600">메시지 추가</p>
                <div className="mb-2 flex items-center gap-2">
                  <select
                    value={newStoryRole}
                    onChange={(e) => setNewStoryRole(e.target.value as "USER" | "AI")}
                    className="border border-slate-300 rounded px-2 py-1 text-xs bg-white"
                  >
                    <option value="USER">USER</option>
                    <option value="AI">AI</option>
                  </select>
                  <button
                    onClick={() => addStoryEntry(storySession.id)}
                    disabled={storyActionLoading}
                    className="rounded bg-violet-600 px-3 py-1 text-xs font-semibold text-white hover:bg-violet-700 disabled:opacity-50"
                  >
                    추가
                  </button>
                </div>
                <textarea
                  value={newStoryContent}
                  onChange={(e) => setNewStoryContent(e.target.value)}
                  rows={3}
                  className="w-full resize-y rounded border border-slate-300 bg-white px-2 py-1 text-sm"
                  placeholder="추가할 스토리 메시지를 입력하세요"
                />
              </div>
            </div>

            <div className="flex-1 space-y-2 overflow-y-auto bg-slate-50/40 p-4 sm:px-6 sm:py-5">
              {storyLoading ? (
                <div className="py-10 text-center text-sm text-slate-400">스토리 불러오는 중...</div>
              ) : storyEntries.length === 0 ? (
                <div className="py-10 text-center text-sm text-slate-400">스토리 메시지가 없습니다.</div>
              ) : (
                storyEntries.map((entry) => (
                  <div key={entry.id} className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                            entry.role === "USER" ? "bg-blue-100 text-blue-700" : "bg-slate-200 text-slate-700"
                          }`}
                        >
                          {entry.role}
                        </span>
                        <span className="text-[10px] text-slate-500">{KST_FORMATTER.format(new Date(entry.created_at))}</span>
                        {entry.judgments && entry.judgments.length > 0 && (
                          <button
                            onClick={() => toggleJudgmentExpand(entry.id)}
                            className="rounded bg-amber-100 px-2 py-0.5 text-[10px] text-amber-700 hover:bg-amber-200 transition-colors cursor-pointer"
                          >
                            행동 {entry.judgments.length}건 {expandedJudgments.has(entry.id) ? "▲" : "▼"}
                          </button>
                        )}
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => startStoryEdit(entry)}
                          disabled={busyStoryLogId === entry.id}
                          className="rounded border border-slate-200 bg-white px-2 py-1 text-xs hover:bg-slate-100 disabled:opacity-50"
                        >
                          수정
                        </button>
                        <button
                          onClick={() => deleteStoryEntry(storySession.id, entry.id)}
                          disabled={busyStoryLogId === entry.id}
                          className="rounded border border-red-200 bg-white px-2 py-1 text-xs text-red-600 hover:bg-red-50 disabled:opacity-50"
                        >
                          삭제
                        </button>
                      </div>
                    </div>

                    {editingStoryLogId === entry.id ? (
                      <div className="space-y-2">
                        <div className="flex flex-wrap gap-2">
                          <select
                            value={storyEditRole}
                            onChange={(e) => setStoryEditRole(e.target.value as "USER" | "AI")}
                            className="border border-slate-300 rounded px-2 py-1 text-xs bg-white"
                          >
                            <option value="USER">USER</option>
                            <option value="AI">AI</option>
                          </select>
                          <button
                            onClick={() => saveStoryEdit(storySession.id, entry.id)}
                            disabled={busyStoryLogId === entry.id}
                            className="rounded bg-emerald-600 px-2 py-1 text-xs text-white hover:bg-emerald-700 disabled:opacity-50"
                          >
                            저장
                          </button>
                          <button
                            onClick={cancelStoryEdit}
                            disabled={busyStoryLogId === entry.id}
                            className="rounded border border-slate-200 bg-white px-2 py-1 text-xs hover:bg-slate-100 disabled:opacity-50"
                          >
                            취소
                          </button>
                        </div>
                        <textarea
                          value={storyEditContent}
                          onChange={(e) => setStoryEditContent(e.target.value)}
                          rows={5}
                          className="w-full resize-y rounded border border-slate-300 bg-white px-2 py-1 text-sm"
                        />
                      </div>
                    ) : (
                      <p className="whitespace-pre-wrap text-sm text-slate-700">{entry.content}</p>
                    )}

                    {entry.judgments && entry.judgments.length > 0 && expandedJudgments.has(entry.id) && (
                      <div className="mt-2 space-y-1.5 border-t border-amber-100 pt-2">
                        {entry.judgments.map((j) => (
                          <div key={j.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded bg-amber-50/70 px-3 py-2 text-xs">
                            <span className="font-semibold text-slate-800">{j.character_name}</span>
                            <span className="text-slate-500 truncate max-w-[200px]" title={j.action_text}>{j.action_text}</span>
                            {j.dice_result != null && (
                              <span className="text-slate-600">
                                🎲 {j.dice_result}{j.modifier !== 0 && `${j.modifier >= 0 ? "+" : ""}${j.modifier}`}{j.final_value != null && ` = ${j.final_value}`}
                              </span>
                            )}
                            <span className="text-slate-400">DC {j.difficulty}</span>
                            <span className={outcomeColor(j.outcome)}>{j.outcome ?? "-"}</span>
                            <button
                              onClick={() => deleteJudgmentEntry(storySession.id, j.id)}
                              disabled={busyJudgmentId === j.id}
                              className="ml-auto rounded border border-red-200 bg-white px-2 py-0.5 text-[10px] text-red-600 hover:bg-red-50 disabled:opacity-50"
                            >
                              메시지 삭제
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
