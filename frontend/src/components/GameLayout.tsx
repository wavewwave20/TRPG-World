import { useEffect, useMemo, useRef, useState } from 'react';
import LeftPane from './LeftPane';
import CenterPane from './CenterPane';
import RightPane from './RightPane';
import JudgmentModal from './JudgmentModal';
import GrowthRewardModal from './GrowthRewardModal';
import { useGameStore } from '../stores/gameStore';
import { useActStore } from '../stores/actStore';
import { useAuthStore } from '../stores/authStore';
import { useSocketStore } from '../stores/socketStore';
import { useChatStore } from '../stores/chatStore';
import { useAIStore } from '../stores/aiStore';
import { useActionStore } from '../stores/actionStore';

export default function GameLayout() {
  const currentSession = useGameStore((state) => state.currentSession);
  const setSession = useGameStore((state) => state.setSession);
  const isJudgmentModalOpen = useGameStore((state) => state.isJudgmentModalOpen);
  const setJudgmentModalOpen = useGameStore((state) => state.setJudgmentModalOpen);
  const userId = useAuthStore((state) => state.userId);
  const emit = useSocketStore((state) => state.emit);
  const socket = useSocketStore((state) => state.socket);
  const clearChat = useChatStore((state) => state.clear);
  const setActionInputDisabled = useActionStore((state) => state.setActionInputDisabled);
  const clearJudgments = useAIStore((state) => state.clearJudgments);
  const judgments = useAIStore((state) => state.judgments);
  const isGenerating = useAIStore((state) => state.isGenerating);
  const isTransitioning = useActStore((state) => state.isTransitioning);
  const transitionCompletedTitle = useActStore((state) => state.transitionCompletedTitle);
  const isHost = !!currentSession && currentSession.hostUserId === userId;
  const narrativeRequestInFlightRef = useRef(false);

  const loadingLines = useMemo(
    () => [
      'NPC들이 대사를 외우는 중...',
      '새로운 함정을 설치하는 중... 잠시만요, 이건 못 본 걸로',
      '몬스터들이 출근 도장을 찍는 중...',
      '다이스 신이 다음 저주를 준비하는 중...',
      '경험치 정산 중... 세금 떼는 중...',
      '시체 담당 스태프가 전투 현장 정리하는 중...',
      '복선 회수팀이 출동하는 중...',
      '여관 주인이 오늘도 떡밥을 흘릴 준비를 하는 중...',
      '다음 동료 NPC가 비극적 과거사를 리허설하는 중...',
      '파티의 흑역사가 바드의 노래에 추가되는 중...',
      '방금 죽은 잡몹의 가족에게 통보하는 중...',
      '길 위의 수상한 노인이 대본 넘기는 중...',
      'NPC 조합에서 위험수당 협상하는 중...',
      '다음 맵 로딩 중... 벽 뒤에 아이템 숨기는 중...',
      '조명팀이 다음 장소 분위기 맞추는 중...',
    ],
    []
  );
  const [loadingLine, setLoadingLine] = useState(loadingLines[0]);

  // Reset per session so each round can request a new narrative stream.
  useEffect(() => {
    narrativeRequestInFlightRef.current = false;
  }, [currentSession?.id]);

  // Keep local request guard in sync with socket lifecycle events.
  useEffect(() => {
    if (!socket) return;

    const handleNarrativeStreamStarted = () => {
      narrativeRequestInFlightRef.current = true;
      setJudgmentModalOpen(false);
    };
    const handleNarrativeStreamFinished = () => {
      narrativeRequestInFlightRef.current = false;
    };

    socket.on('narrative_stream_started', handleNarrativeStreamStarted);
    socket.on('narrative_complete', handleNarrativeStreamFinished);
    socket.on('narrative_error', handleNarrativeStreamFinished);

    return () => {
      socket.off('narrative_stream_started', handleNarrativeStreamStarted);
      socket.off('narrative_complete', handleNarrativeStreamFinished);
      socket.off('narrative_error', handleNarrativeStreamFinished);
    };
  }, [socket, setJudgmentModalOpen]);

  // Session heartbeat: every 5s while inside a session page
  useEffect(() => {
    if (!currentSession || !userId) return;

    // Send an immediate heartbeat on mount
    emit('session_heartbeat', { session_id: currentSession.id, user_id: userId });

    const interval = setInterval(() => {
      emit('session_heartbeat', { session_id: currentSession.id, user_id: userId });
    }, 5000);

    return () => {
      clearInterval(interval);
    };
  }, [currentSession, userId, emit]);

  // Handle session_ended event
  useEffect(() => {
    if (!socket || !currentSession) return;

    const handleSessionEnded = (data: { 
      session_id: number; 
      reason: string;
    }) => {
      // Only handle if it's for the current session
      if (currentSession.id !== data.session_id) return;

      // Session teardown (character selection is preserved).
      clearChat();
      setActionInputDisabled(false);
      clearJudgments();
      setSession(null);
      // Note: Don't clear character here - character selection should persist
      // across sessions so users can rejoin or join other sessions

      // Note: Redirect to session list is handled by App.tsx
      // When currentSession becomes null, showLobby becomes true
    };

    socket.on('session_ended', handleSessionEnded);

    return () => {
      socket.off('session_ended', handleSessionEnded);
    };
  }, [socket, currentSession, clearChat, clearJudgments, setActionInputDisabled, setSession]);

  // Handle judgment modal open/close based on WebSocket events
  // Open the judgment modal when the round enters the judgment phase.
  useEffect(() => {
    if (!socket || !currentSession) return;

    // Open modal when judgment phase starts
    // The judgment phase starts when either:
    // 1. judgment_ready - for the player who submitted the action
    // 2. player_action_analyzed - for other players observing
    const handleJudgmentReady = () => {
      setJudgmentModalOpen(true);
    };

    const handlePlayerActionAnalyzed = () => {
      setJudgmentModalOpen(true);
    };

    // Register event handlers
    socket.on('judgment_ready', handleJudgmentReady);
    socket.on('player_action_analyzed', handlePlayerActionAnalyzed);

    // Cleanup on unmount
    return () => {
      socket.off('judgment_ready', handleJudgmentReady);
      socket.off('player_action_analyzed', handlePlayerActionAnalyzed);
    };
  }, [socket, currentSession, setJudgmentModalOpen]);

  const [activeTab, setActiveTab] = useState<'character' | 'story' | 'chat'>('story');

  const handleJudgmentModalClose = () => {
    if (currentSession) {
      const allComplete = judgments.length > 0 && judgments.every((j) => j.status === 'complete');

      // Desired UX: when the whole judgment modal closes after completion,
      // immediately reveal the pre-generated narrative stream.
      if (
        allComplete &&
        isHost &&
        !isGenerating &&
        !narrativeRequestInFlightRef.current
      ) {
        narrativeRequestInFlightRef.current = true;
        emit('request_narrative_stream', { session_id: currentSession.id });
      }
    }

    setJudgmentModalOpen(false);
  };

  useEffect(() => {
    if (!isTransitioning || transitionCompletedTitle) return;

    let pool = [...loadingLines];
    const pick = () => {
      if (pool.length === 0) pool = [...loadingLines];
      const idx = Math.floor(Math.random() * pool.length);
      const [line] = pool.splice(idx, 1);
      setLoadingLine(line);
    };

    pick();
    const timer = setInterval(pick, 1400);
    return () => clearInterval(timer);
  }, [isTransitioning, transitionCompletedTitle, loadingLines]);

  return (
    <>
      {/* Desktop: 3-column grid (unchanged) */}
      <div className="h-full w-full hidden lg:grid grid-cols-12 gap-6 p-6">
        {/* Left: Character Status (25%) */}
        <div className="col-span-3 bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
          <LeftPane />
        </div>

        {/* Center: Story View (50%) */}
        <div className="col-span-6 bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col relative">
          <CenterPane />
        </div>

        {/* Right: Chat (25%) */}
        <div className="col-span-3 border border-slate-200 bg-white rounded-xl shadow-sm overflow-hidden flex flex-col">
          <RightPane />
        </div>
      </div>

      {/* Mobile/Tablet: Single pane with bottom tabs */}
      <div className="h-full w-full flex flex-col lg:hidden">
        {/* Active pane content - all mounted, hidden/shown via CSS */}
        <div className={`flex-1 overflow-hidden ${activeTab === 'character' ? 'flex flex-col' : 'hidden'}`}>
          <div className="h-full bg-white overflow-hidden flex flex-col">
            <LeftPane />
          </div>
        </div>
        <div className={`flex-1 overflow-hidden ${activeTab === 'story' ? 'flex flex-col' : 'hidden'}`}>
          <div className="h-full bg-white overflow-hidden flex flex-col relative">
            <CenterPane />
          </div>
        </div>
        <div className={`flex-1 overflow-hidden ${activeTab === 'chat' ? 'flex flex-col' : 'hidden'}`}>
          <div className="h-full bg-white overflow-hidden flex flex-col">
            <RightPane />
          </div>
        </div>

        {/* Bottom Tab Bar */}
        <nav className="flex-none h-14 bg-white border-t border-slate-200 flex items-stretch safe-area-bottom">
          <button
            onClick={() => setActiveTab('character')}
            className={`flex-1 flex flex-col items-center justify-center gap-0.5 transition-colors ${
              activeTab === 'character'
                ? 'text-blue-600 border-t-2 border-blue-600 -mt-px'
                : 'text-slate-400 hover:text-slate-600'
            }`}
            aria-current={activeTab === 'character' ? 'page' : undefined}
          >
            <span className="text-lg">◈</span>
            <span className="text-[10px] font-semibold">캐릭터</span>
          </button>
          <button
            onClick={() => setActiveTab('story')}
            className={`flex-1 flex flex-col items-center justify-center gap-0.5 transition-colors ${
              activeTab === 'story'
                ? 'text-blue-600 border-t-2 border-blue-600 -mt-px'
                : 'text-slate-400 hover:text-slate-600'
            }`}
            aria-current={activeTab === 'story' ? 'page' : undefined}
          >
            <span className="text-lg">📜</span>
            <span className="text-[10px] font-semibold">스토리</span>
          </button>
          <button
            onClick={() => setActiveTab('chat')}
            className={`flex-1 flex flex-col items-center justify-center gap-0.5 transition-colors ${
              activeTab === 'chat'
                ? 'text-blue-600 border-t-2 border-blue-600 -mt-px'
                : 'text-slate-400 hover:text-slate-600'
            }`}
            aria-current={activeTab === 'chat' ? 'page' : undefined}
          >
            <span className="text-lg">💬</span>
            <span className="text-[10px] font-semibold">채팅</span>
          </button>
        </nav>
      </div>

      {isTransitioning && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center">
          <div className="absolute inset-0 bg-black/65 backdrop-blur-sm transition-opacity duration-500" />
          <div className="relative mx-4 w-full max-w-lg rounded-2xl border border-white/20 bg-slate-900/90 text-white shadow-2xl p-6 text-center transition-all duration-700 ease-out">
            {!transitionCompletedTitle ? (
              <div className="transition-opacity duration-500 opacity-100">
                <div className="text-xs uppercase tracking-[0.2em] text-amber-300 mb-2">Act Transition</div>
                <div className="text-lg font-bold mb-3">다음 막을 준비하고 있습니다</div>
                <div className="text-sm text-slate-200 transition-all duration-500">{loadingLine}</div>
              </div>
            ) : (
              <div className="transition-all duration-700 opacity-100 scale-100">
                <div className="text-xs uppercase tracking-[0.2em] text-emerald-300 mb-3">Act Ready</div>
                {(() => {
                  const lines = transitionCompletedTitle.split('\n');
                  return (
                    <>
                      <div className="text-lg sm:text-xl font-bold text-amber-300 mb-1">{lines[0]}</div>
                      {lines[1] && <div className="text-2xl sm:text-3xl font-extrabold tracking-tight">{lines[1]}</div>}
                      {lines[2] && <div className="text-base sm:text-lg font-semibold text-slate-300 mt-1">{lines[2]}</div>}
                    </>
                  );
                })()}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Judgment Modal */}
      <JudgmentModal
        isOpen={isJudgmentModalOpen}
        onClose={handleJudgmentModalClose}
        sessionId={currentSession?.id || 0}
      />

      {/* Growth Reward Modal */}
      <GrowthRewardModal />
    </>
  );
}
