import { useState, useEffect, useCallback, useRef } from 'react';
import { useGameStore } from '../stores/gameStore';
import { useSocketStore } from '../stores/socketStore';
import { useAuthStore } from '../stores/authStore';
import { useChatStore } from '../stores/chatStore';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';
const SESSION_POLL_VISIBLE_MS = 15000;
const SESSION_POLL_HIDDEN_MS = 60000;

interface Session {
  id: number;
  title: string;
  host_user_id: number;
  participant_count: number;
  created_at: string;
  is_active: boolean;
}

interface SessionParticipantsUpdate {
  session_id: number;
  participant_count?: number;
  participants?: Array<{ user_id: number; character_id: number; character_name: string }>;
}

interface SessionListProps {
  onJoinSuccess?: () => void;
}

export default function SessionList({ onJoinSuccess }: SessionListProps) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState('');
  const [isJoining, setIsJoining] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const pollTimerRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  
  const setSession = useGameStore((state) => state.setSession);
  const currentSession = useGameStore((state) => state.currentSession);
  const clearNotifications = useGameStore((state) => state.clearNotifications);
  const currentCharacter = useGameStore((state) => state.currentCharacter);
  const joinSession = useSocketStore((state) => state.joinSession);
  const leaveSession = useSocketStore((state) => state.leaveSession);
  const connected = useSocketStore((state) => state.connected);
  const socket = useSocketStore((state) => state.socket);
  const userId = useAuthStore((state) => state.userId);
  const clearChat = useChatStore((state) => state.clear);

  const loadSessions = useCallback(async (options?: { showRefreshing?: boolean }) => {
    const showRefreshing = options?.showRefreshing ?? false;
    const controller = new AbortController();

    // Abort stale in-flight request and keep only latest one.
    abortRef.current?.abort();
    abortRef.current = controller;

    try {
      if (showRefreshing) {
        setRefreshing(true);
      }
      const response = await fetch(`${API_BASE_URL}/api/sessions/`, { signal: controller.signal });
      if (response.ok) {
        const data = await response.json();
        // Filter to only show active sessions (backend already filters, but double-check)
        const activeSessions = data.filter((session: Session) => session.is_active !== false);
        setSessions(activeSessions);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return;
      }
      console.error('Failed to load sessions:', err);
    } finally {
      if (abortRef.current === controller) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    const refreshNow = () => {
      void loadSessions();
    };

    const startPolling = () => {
      if (pollTimerRef.current !== null) {
        window.clearInterval(pollTimerRef.current);
      }
      const intervalMs =
        document.visibilityState === 'visible' ? SESSION_POLL_VISIBLE_MS : SESSION_POLL_HIDDEN_MS;
      pollTimerRef.current = window.setInterval(() => {
        void loadSessions();
      }, intervalMs);
    };

    refreshNow();
    startPolling();

    const handleVisibilityChange = () => {
      refreshNow();
      startPolling();
    };

    window.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      if (pollTimerRef.current !== null) {
        window.clearInterval(pollTimerRef.current);
      }
      abortRef.current?.abort();
      window.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [loadSessions]);

  // Listen for session_ended events to update the session list
  useEffect(() => {
    if (!socket) return;

    const handleSessionEnded = (data: { session_id: number; reason?: string }) => {
      // Remove the ended session from the list immediately
      setSessions((prevSessions) => 
        prevSessions.filter((session) => session.id !== data.session_id)
      );
    };

    const handleUserJoined = (data: SessionParticipantsUpdate) => {
      // Update participant count when a user joins
      const participantCount = data.participant_count;
      if (participantCount === undefined) return;
      setSessions((prevSessions) =>
        prevSessions.map((session) =>
          session.id === data.session_id
            ? { ...session, participant_count: participantCount }
            : session
        )
      );
    };

    const handleUserLeft = (data: SessionParticipantsUpdate) => {
      // Update participant count when a user leaves
      const participantCount = data.participant_count;
      if (participantCount === undefined) return;
      setSessions((prevSessions) =>
        prevSessions.map((session) =>
          session.id === data.session_id
            ? { ...session, participant_count: participantCount }
            : session
        )
      );
    };

    socket.on('session_ended', handleSessionEnded);
    socket.on('user_joined', handleUserJoined);
    socket.on('user_left', handleUserLeft);

    return () => {
      socket.off('session_ended', handleSessionEnded);
      socket.off('user_joined', handleUserJoined);
      socket.off('user_left', handleUserLeft);
    };
  }, [socket]);

  const handleJoinSession = async (id: number, title: string, hostUserId: number) => {
    setError(null);
    
    if (!connected) {
      setError('소켓이 연결되지 않았습니다. 잠시 후 다시 시도하세요.');
      return;
    }

    if (!currentCharacter) {
      setError('캐릭터를 먼저 선택해주세요.');
      return;
    }

    if (!userId) {
      setError('로그인이 필요합니다.');
      return;
    }

    setIsJoining(true);

    try {
      // If already in another session, leave it (API + socket) and clear logs
      if (currentSession && currentSession.id !== id && userId) {
        try {
          await fetch(`${API_BASE_URL}/api/sessions/${currentSession.id}/leave?user_id=${userId}`, { method: 'POST' });
        } catch (e) {
          console.warn('Failed to call leave API for previous session:', e);
        }
        leaveSession(currentSession.id, userId);
      }

      // Clear chat and system logs before joining
      clearChat();
      clearNotifications();
      
      // Call join session API
      const response = await fetch(`${API_BASE_URL}/api/sessions/${id}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          character_id: currentCharacter.id
        })
      });

      if (!response.ok) {
        let detail = 'Failed to join session';
        try {
          const data = await response.json();
          detail = data?.detail || detail;
        } catch {
          // ignore JSON parse errors
        }
        const normalized = String(detail).toLowerCase();
        const isAlreadyJoinedError =
          response.status === 400 &&
          (normalized.includes('already joined') || normalized.includes('이미 참가'));

        if (!isAlreadyJoinedError) {
          throw new Error(detail);
        }
      }
      
      // Update game store with session info
      setSession({
        id: id,
        title: title,
        hostUserId: hostUserId
      });
      
      // Emit join_session socket event with character_id
      joinSession(id, userId, currentCharacter.id);
      
      // Call success callback if provided
      if (onJoinSuccess) {
        onJoinSuccess();
      }
    } catch (err) {
      if (err instanceof Error) {
        setError(`세션 참가 실패: ${err.message}`);
      } else {
        setError('세션 참가 실패: 알 수 없는 오류');
      }
    } finally {
      setIsJoining(false);
    }
  };

  const handleJoinById = async (e: React.FormEvent) => {
    e.preventDefault();
    
    setError(null);
    
    // Validate session ID
    const id = parseInt(sessionId.trim());
    if (isNaN(id) || id <= 0) {
      setError('유효한 세션 ID를 입력하세요');
      return;
    }

    // Find session in list
    const session = sessions.find(s => s.id === id);
    if (session) {
      await handleJoinSession(id, session.title, session.host_user_id);
      setSessionId('');
    } else {
      setError('세션을 찾을 수 없습니다.');
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-card hover:shadow-card-hover transition-all duration-300 h-full flex flex-col">
      <div className="mb-6 pb-4 border-b border-slate-100">
        <h3 className="text-xl font-bold text-slate-800 flex items-center gap-2">
          <span className="text-2xl">🚀</span> 세션 참가
        </h3>
        <p className="text-slate-500 text-sm mt-1">
          {currentCharacter ? `플레이 캐릭터: ${currentCharacter.name}` : '먼저 캐릭터를 선택하세요'}
        </p>
      </div>

      {/* Session List */}
      <div className="mb-6 flex flex-col">
        <div className="mb-2 flex items-center justify-end">
          <button
            onClick={() => loadSessions({ showRefreshing: true })}
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
        <h4 className="text-sm font-semibold text-slate-700 mb-3">활성 세션</h4>
        <div className="overflow-y-auto" style={{ maxHeight: '400px' }}>
          {loading ? (
            <div className="text-center py-8 text-slate-400">로딩 중...</div>
          ) : sessions.length === 0 ? (
            <div className="text-center py-8 text-slate-400">활성 세션이 없습니다</div>
          ) : (
            <div className="space-y-2 pr-2">
              {sessions.map((session) => (
              <div
                key={session.id}
                className="bg-slate-50 border border-slate-200 rounded-lg p-4 hover:border-blue-300 transition-colors"
              >
                <div className="flex justify-between items-start mb-2">
                  <div className="flex-1">
                    <h5 className="font-semibold text-slate-800">{session.title}</h5>
                    <p className="text-xs text-slate-500">Session #{session.id}</p>
                  </div>
                  <span className="bg-blue-100 text-blue-700 text-xs px-2 py-1 rounded">
                    {session.participant_count}명
                  </span>
                </div>
                <button
                  onClick={() => handleJoinSession(session.id, session.title, session.host_user_id)}
                  disabled={isJoining || !currentCharacter}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white px-3 py-2 rounded text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                >
                  참가
                </button>
              </div>
            ))}
            </div>
          )}
        </div>
      </div>
      
      {/* Join by ID Form */}
      <form onSubmit={handleJoinById} className="space-y-4 border-t border-slate-200 pt-4">
        <div className="space-y-1.5">
          <label htmlFor="session-id" className="block text-sm font-semibold text-slate-700">
            또는 ID로 참가
          </label>
          <div className="relative">
            <input
              id="session-id"
              type="text"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              placeholder="e.g., 101"
              className="w-full bg-slate-50 border border-slate-200 text-slate-900 px-4 py-2 pl-10 rounded-lg text-sm font-mono focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all placeholder:text-slate-400"
              disabled={isJoining}
            />
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-bold">#</div>
          </div>
        </div>
        
        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-100 text-red-700 px-4 py-3 rounded-lg text-sm flex items-start gap-2">
            <span>⚠️</span> {error}
          </div>
        )}
        
        <button
          type="submit"
          disabled={isJoining || !connected || !sessionId.trim() || !currentCharacter}
          className="w-full bg-white text-blue-600 border-2 border-blue-100 hover:border-blue-500 hover:bg-blue-50 px-4 py-2 rounded-lg text-sm font-bold transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
        >
          {isJoining ? '연결 중...' : 'ID로 참가'}
        </button>
      </form>
    </div>
  );
}
