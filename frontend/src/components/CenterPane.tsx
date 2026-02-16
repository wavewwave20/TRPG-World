import { memo, useCallback, useState, useEffect, useMemo, useRef } from 'react';
import { useGameStore } from '../stores/gameStore';
import { useSocketStore } from '../stores/socketStore';
import { useActionStore } from '../stores/actionStore';
import { useStoryStore } from '../stores/storyStore';
import { useAuthStore } from '../stores/authStore';
import { useAIStore } from '../stores/aiStore';
import { getStoryLogs, getCurrentAct } from '../services/api';
// SessionCreationForm removed from in-session view
import ModerationModal from './ModerationModal';
import ActBanner from './ActBanner';
import { useActStore } from '../stores/actStore';
// import TypingText from './TypingText'; // Currently unused
// import AIGenerationIndicator from './AIGenerationIndicator'; // REMOVED for streaming optimization
import JudgmentResultsButton from './JudgmentResultsButton';
import type { JudgmentSummary } from '../services/api';
import type { JudgmentSetup, JudgmentResult } from '../types/judgment';
import { isJudgmentResult } from '../types/judgment';

/**
 * **text** 패턴을 <strong> 태그로 변환하는 렌더러.
 * 마크다운 중 볼드체만 지원합니다.
 */
function renderBoldText(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-bold">{part.slice(2, -2)}</strong>;
    }
    return <span key={i}>{part}</span>;
  });
}

interface StoryEntryForRender {
  id: number;
  role: 'USER' | 'AI';
  content: string;
  judgments?: JudgmentSummary[] | null;
  event_triggered?: boolean;
}

interface StoryEntryItemProps {
  entry: StoryEntryForRender;
  currentCharacterId?: number;
  onOpenJudgmentModal: () => void;
}

const StoryEntryItem = memo(function StoryEntryItem({
  entry,
  currentCharacterId,
  onOpenJudgmentModal,
}: StoryEntryItemProps) {
  const entryJudgments = entry.judgments ?? [];
  const allCompleteForEntry =
    entryJudgments.length > 0 &&
    entryJudgments.every((j) => j.dice_result !== null && j.outcome !== null);
  const myCompletedForEntry = currentCharacterId
    ? entryJudgments.some(
        (j) => j.character_id === currentCharacterId && j.dice_result !== null && j.outcome !== null
      )
    : false;
  const showOpenModal = !allCompleteForEntry && !myCompletedForEntry;

  return (
    <div
      className={`flex flex-col max-w-full sm:max-w-3xl ${
        entry.role === 'USER' ? 'ml-auto items-end' : 'mr-auto items-start'
      }`}
    >
      <div
        className={`text-[10px] font-bold uppercase tracking-wider mb-1 px-1 ${
          entry.role === 'USER' ? 'text-blue-600' : 'text-slate-500'
        }`}
      >
        {entry.role === 'USER' ? '모험가들' : '던전 마스터'}
      </div>

      <div
        className={`px-4 py-3 sm:px-6 sm:py-4 rounded-2xl shadow-sm text-sm leading-relaxed whitespace-pre-wrap max-w-full ${
          entry.role === 'USER'
            ? 'bg-blue-50 text-slate-800 border border-blue-100 rounded-tr-none'
            : 'bg-white text-slate-700 border border-slate-200 rounded-tl-none font-serif'
        }`}
      >
        {entry.role === 'AI' && entry.event_triggered && (
          <div className="mb-2">
            <span className="inline-block bg-amber-100 text-amber-800 text-[11px] font-bold px-2 py-0.5 rounded-full border border-amber-300">
              돌발 이벤트 발생
            </span>
          </div>
        )}
        {renderBoldText(entry.content)}

        {/* Show judgment results button for USER messages with judgments */}
        {entry.role === 'USER' && entry.judgments && entry.judgments.length > 0 && (
          <JudgmentResultsButton
            judgments={entry.judgments}
            onOpenModal={showOpenModal ? onOpenJudgmentModal : undefined}
          />
        )}
      </div>
    </div>
  );
});

function mapAijudgmentToSummary(judgment: JudgmentSetup | JudgmentResult, index: number): JudgmentSummary {
  const rolled = isJudgmentResult(judgment);
  return {
    // Negative IDs mark ephemeral client-side judgments, and remain stable per action.
    id: -(Math.abs(judgment.action_id) + index + 1),
    character_id: judgment.character_id,
    character_name: judgment.character_name,
    action_text: judgment.action_text,
    action_type: null,
    dice_result: rolled ? judgment.dice_result : null,
    modifier: judgment.modifier ?? 0,
    final_value: rolled ? judgment.final_value : null,
    difficulty: judgment.difficulty,
    outcome: rolled ? judgment.outcome : null,
  };
}

export default function CenterPane() {
  const [actionText, setActionText] = useState('');
  const [showModerationModal, setShowModerationModal] = useState(false);
  
  const currentSession = useGameStore((state) => state.currentSession);
  const currentCharacter = useGameStore((state) => state.currentCharacter);
  const isJudgmentModalOpen = useGameStore((state) => state.isJudgmentModalOpen);
  const setJudgmentModalOpen = useGameStore((state) => state.setJudgmentModalOpen);
  const emit = useSocketStore((state) => state.emit);
  
  const actionInputDisabled = useActionStore((state) => state.actionInputDisabled);
  const queueCount = useActionStore((state) => state.queueCount);
  
  const entries = useStoryStore((state) => state.entries);
  const setEntries = useStoryStore((state) => state.setEntries);
  
  const currentUserId = useAuthStore((state) => state.userId);
  
  const isGenerating = useAIStore((state) => state.isGenerating);
  const judgments = useAIStore((state) => state.judgments);
  const currentNarrative = useAIStore((state) => state.currentNarrative);
  const eventTriggered = useAIStore((state) => state.eventTriggered);
  const currentSessionId = currentSession?.id ?? null;
  
  const storyEndRef = useRef<HTMLDivElement>(null);
  const actionInputRef = useRef<HTMLTextAreaElement>(null);
  const narrativeEndRef = useRef<HTMLDivElement>(null);
  const socket = useSocketStore((state) => state.socket);
  const isInitialLoadRef = useRef<boolean>(true);
  const prevJudgmentModalOpenRef = useRef<boolean>(isJudgmentModalOpen);
  const judgmentModalClosedAtRef = useRef<number | null>(null);
  const pendingNarrativeStartScrollRef = useRef<boolean>(false);
  
  // Check if current user is host (number/string mismatch 안전 처리)
  const isHost =
    currentSession?.hostUserId !== undefined &&
    currentSession?.hostUserId !== null &&
    currentUserId !== null &&
    currentUserId !== undefined &&
    Number(currentSession.hostUserId) === Number(currentUserId);
  const currentCharacterId = currentCharacter?.id;
  const allJudgmentsComplete = useMemo(
    () => judgments.length > 0 && judgments.every((j) => j.status === 'complete'),
    [judgments]
  );
  const hasUnresolvedRoundFromLogs = useMemo(() => {
    if (!entries || entries.length === 0) return false;
    const last = entries[entries.length - 1];
    return last.role === 'USER';
  }, [entries]);
  const hostCanAdvanceStory =
    !!isHost &&
    !!currentSession &&
    (judgments.length > 0 || hasUnresolvedRoundFromLogs);
  const openJudgmentModal = useCallback(() => {
    setJudgmentModalOpen(true);
  }, [setJudgmentModalOpen]);

  // Load story logs on session change using getStoryLogs API
  useEffect(() => {
    if (!currentSessionId) {
      setEntries([]);
      isInitialLoadRef.current = false;
      return;
    }

    // 세션 전환/재입장 시 이전 라운드의 로컬 AI 상태를 정리
    useAIStore.getState().setGenerating(false);
    useAIStore.getState().clearCurrentNarrative();

    // Mark next entries change as initial load for auto-scroll
    isInitialLoadRef.current = true;

    let cancelled = false;
    const sessionId = currentSessionId;

    getStoryLogs(sessionId)
      .then((data) => {
        if (!cancelled) {
          setEntries(data.logs);
          if (isInitialLoadRef.current) {
            requestAnimationFrame(() => {
              storyEndRef.current?.scrollIntoView({ behavior: 'smooth' });
            });
            isInitialLoadRef.current = false;
          }
        }
      })
      .catch((error) => {
        if (!cancelled) {
          console.error('Failed to load story logs:', error);
          isInitialLoadRef.current = false;
        }
      });

    return () => {
      cancelled = true;
    };
  }, [currentSessionId, setEntries]);

  // Load current act on session change
  const setCurrentAct = useActStore((state) => state.setCurrentAct);
  useEffect(() => {
    if (!currentSessionId) {
      setCurrentAct(null);
      return;
    }

    let cancelled = false;
    const sessionId = currentSessionId;

    getCurrentAct(sessionId)
      .then((act) => {
        if (cancelled) return;
        if (act) {
          setCurrentAct({
            id: act.id,
            actNumber: act.act_number,
            title: act.title,
            subtitle: act.subtitle,
            startedAt: act.started_at,
          });
        } else {
          setCurrentAct(null);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          console.error('Failed to load current act:', error);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [currentSessionId, setCurrentAct]);

  // Reload story logs when narrative streaming completes
  useEffect(() => {
    const handleStoryLogsUpdated = (event: CustomEvent<{ session_id: number }>) => {
      if (currentSessionId && event.detail.session_id === currentSessionId) {
        getStoryLogs(currentSessionId)
          .then((data) => {
            setEntries(data.logs);
            const aiState = useAIStore.getState();
            if (!aiState.isGenerating && (aiState.currentNarrative.length > 0 || aiState.judgments.length > 0)) {
              aiState.clearJudgments();
            }
          })
          .catch((error) => {
            console.error('Failed to reload story logs:', error);
          });
      }
    };

    window.addEventListener('story_logs_updated', handleStoryLogsUpdated as EventListener);
    return () => {
      window.removeEventListener('story_logs_updated', handleStoryLogsUpdated as EventListener);
    };
  }, [currentSessionId, setEntries]);

  // Track "just closed" timing for judgment modal.
  useEffect(() => {
    const wasOpen = prevJudgmentModalOpenRef.current;
    if (wasOpen && !isJudgmentModalOpen) {
      judgmentModalClosedAtRef.current = Date.now();
    }
    if (isJudgmentModalOpen) {
      judgmentModalClosedAtRef.current = null;
    }
    prevJudgmentModalOpenRef.current = isJudgmentModalOpen;
  }, [isJudgmentModalOpen]);

  // One-time scroll right after first narrative token arrives.
  useEffect(() => {
    if (!pendingNarrativeStartScrollRef.current) return;
    if (!currentNarrative) return;

    requestAnimationFrame(() => {
      storyEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    });
    pendingNarrativeStartScrollRef.current = false;
  }, [currentNarrative]);

  // Auto-scroll only right after streaming starts.
  useEffect(() => {
    if (!socket || !currentSessionId) return;

    const shouldHandleStreamEvent = (eventSessionId?: number) => {
      if (!eventSessionId) return true;
      return eventSessionId === currentSessionId;
    };

    const scrollToBottom = () => {
      requestAnimationFrame(() => {
        storyEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      });
    };

    const handleStreamingStarted = (data?: { session_id?: number }) => {
      if (!shouldHandleStreamEvent(data?.session_id)) return;
      const modalOpenNow = useGameStore.getState().isJudgmentModalOpen;
      const closedAt = judgmentModalClosedAtRef.current;
      const closedRecently = closedAt !== null && Date.now() - closedAt <= 5000;
      if (!modalOpenNow && !closedRecently) return;
      pendingNarrativeStartScrollRef.current = true;
      if (useAIStore.getState().currentNarrative) {
        scrollToBottom();
        pendingNarrativeStartScrollRef.current = false;
      }
      judgmentModalClosedAtRef.current = null;
    };

    socket.on('narrative_stream_started', handleStreamingStarted);
    socket.on('story_generation_started', handleStreamingStarted);

    return () => {
      socket.off('narrative_stream_started', handleStreamingStarted);
      socket.off('story_generation_started', handleStreamingStarted);
    };
  }, [socket, currentSessionId]);

  // Derive client-side judgment projection without mutating the story store.
  const displayEntries = useMemo(() => {
    if (!entries || entries.length === 0) return entries;
    if (!judgments || judgments.length === 0) return entries;

    let lastUserIndex = -1;
    for (let i = entries.length - 1; i >= 0; i--) {
      if (entries[i].role === 'USER') {
        lastUserIndex = i;
        break;
      }
    }
    if (lastUserIndex === -1) return entries;

    const target = entries[lastUserIndex];
    const hasBackendJudgments =
      !!target.judgments &&
      target.judgments.length > 0 &&
      target.judgments.every((j) => j.id > 0);
    if (hasBackendJudgments) return entries;

    const mapped = judgments.map((judgment, index) => mapAijudgmentToSummary(judgment, index));
    const next = entries.slice();
    next[lastUserIndex] = { ...target, judgments: mapped };
    return next;
  }, [entries, judgments]);

  // Listen for story_committed event to clear the local action draft and refocus input
  useEffect(() => {
    const socket = useSocketStore.getState().socket;
    
    if (!socket) return;
    
    const handleStoryCommitted = () => {
      // Clear action input text
      setActionText('');
      
      // Focus input field
      actionInputRef.current?.focus();
    };
    socket.on('story_committed', handleStoryCommitted);
    
    // Cleanup listener on unmount
    return () => {
      socket.off('story_committed', handleStoryCommitted);
    };
  }, []);

  // Leaving handled via App header back button

  const handleStartGame = () => {
    if (!currentSession) return;
    emit('start_game', { session_id: currentSession.id });
  };

  const handleHostAdvanceStory = useCallback(() => {
    if (!currentSession) return;
    if (!allJudgmentsComplete) {
      const confirmed = window.confirm('아직 완료되지 않은 판정을 모두 확정하고 이야기를 진행할까요?');
      if (!confirmed) return;
    }
    emit('request_narrative_stream', {
      session_id: currentSession.id,
      force: !allJudgmentsComplete,
    });
  }, [currentSession, allJudgmentsComplete, emit]);

  const handleSubmitAction = () => {
    // Validate action text is non-empty
    if (!actionText.trim()) {
      return;
    }
    
    // Ensure we have session and character
    if (!currentSession || !currentCharacter || !currentUserId) {
      return;
    }
    
    // Submit action to queue - host will commit all actions together
    // This does NOT trigger LLM immediately, just adds to the action queue
    emit('submit_action', {
      session_id: currentSession.id,
      player_id: currentUserId,
      character_name: currentCharacter.name,
      action_text: actionText.trim()
    });
    
    // Clear input text after submission
    setActionText('');
    
    // Keep input enabled so player can submit more actions if needed
    // Input will be disabled when host commits actions
  };

  const autoResizeActionInput = useCallback(() => {
    const textarea = actionInputRef.current;
    if (!textarea) return;

    const maxHeight = 192; // about 8 lines with current typography
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`;
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? 'auto' : 'hidden';
  }, []);

  useEffect(() => {
    autoResizeActionInput();
  }, [actionText, autoResizeActionInput]);

  const handleActionInputKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== 'Enter') return;
    // Preserve IME composition behavior (Korean/Japanese/etc.)
    if (e.nativeEvent.isComposing) return;
    if (e.shiftKey) return; // Shift+Enter => newline

    e.preventDefault();
    handleSubmitAction();
  };

  return (
    <div className="h-full flex flex-col relative z-10 bg-white">
      <div className="flex justify-between items-center px-3 py-3 sm:px-6 sm:py-4 border-b border-slate-200 bg-white sticky top-0 z-20">
        <h2 className="text-lg font-bold text-slate-800">
          스토리북
        </h2>
        
        {/* Session Info or Create Button */}
        {currentSession ? (
          <div className="flex items-center gap-3">
            {/* Moderation Button - Only show when user is host */}
            {isHost && (
              <>
                <button
                  onClick={() => setShowModerationModal(true)}
                  className="relative bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 px-3 py-2.5 lg:py-1.5 rounded-lg text-xs font-semibold shadow-sm transition-all hover:border-slate-300"
                >
                  행동 결정
                  {/* Queue count badge - Show when queueCount > 0 */}
                  {queueCount > 0 && (
                    <span className="absolute -top-2 -right-2 bg-red-500 text-white text-[10px] font-bold rounded-full h-5 w-5 flex items-center justify-center shadow-sm border border-white">
                      {queueCount}
                    </span>
                  )}
                </button>

                {hostCanAdvanceStory && (
                  <button
                    onClick={handleHostAdvanceStory}
                    disabled={isGenerating}
                    className="bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-300 px-3 py-2.5 lg:py-1.5 rounded-lg text-xs font-semibold shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isGenerating
                      ? '이야기 생성 중...'
                      : allJudgmentsComplete
                      ? '스토리 진행'
                      : '판정 건너뛰고 스토리 진행'}
                  </button>
                )}
              </>
            )}
          </div>
        ) : (
          <div />
        )}
      </div>
      
      {/* Session Creation Form removed from in-session view */}
      
      {/* Act Banner */}
      {currentSession && <ActBanner />}

      {/* Story Content Section */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4 sm:p-6 sm:space-y-6 scroll-smooth bg-slate-50/50 relative">
        {/* AI Generation Indicator - REMOVED for streaming optimization */}
        {/* <AIGenerationIndicator isGenerating={isGenerating} /> */}
        
        {currentSession ? (
          <>
            {displayEntries.length === 0 && !currentNarrative ? (
              <div className="flex flex-col items-center justify-center h-48 text-slate-400 text-center">
                <div className="text-4xl mb-3">📜</div>
                <p>스토리북이 비어있습니다. 당신의 모험이 쓰여지길 기다립니다...</p>
                {isHost && (
                  <button
                    onClick={handleStartGame}
                    disabled={isGenerating}
                    className="mt-4 bg-emerald-600 hover:bg-emerald-700 text-white px-6 py-2.5 rounded-lg text-sm font-bold shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isGenerating ? '이야기 생성 중...' : '게임 시작'}
                  </button>
                )}
              </div>
            ) : (
              displayEntries.map((entry) => {
                return (
                  <StoryEntryItem
                    key={entry.id}
                    entry={entry}
                    currentCharacterId={currentCharacterId}
                    onOpenJudgmentModal={openJudgmentModal}
                  />
                );
              })
            )}
            
            {/* Streaming Narrative - show at the bottom when narrative is being generated */}
            {currentNarrative && (
              <div className="flex flex-col max-w-full sm:max-w-3xl mr-auto items-start">
                <div className="text-[10px] font-bold uppercase tracking-wider mb-1 px-1 text-slate-500">
                  던전 마스터
                </div>
                <div className="px-4 py-3 sm:px-6 sm:py-4 rounded-2xl shadow-sm text-sm leading-relaxed whitespace-pre-wrap max-w-full bg-white text-slate-700 border border-slate-200 rounded-tl-none font-serif">
                  {eventTriggered && (
                    <div className="mb-2">
                      <span className="inline-block bg-amber-100 text-amber-800 text-[11px] font-bold px-2 py-0.5 rounded-full border border-amber-300">
                        돌발 이벤트 발생
                      </span>
                    </div>
                  )}
                  <span>{renderBoldText(currentNarrative)}</span>
                  {isGenerating && <span className="inline-block w-2 h-4 ml-0.5 bg-slate-400 animate-pulse align-middle" />}
                </div>
              </div>
            )}
            <div ref={narrativeEndRef} />
            <div ref={storyEndRef} />
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-slate-400">
            <h3 className="text-xl font-bold mb-2 text-slate-600">활성 세션 없음</h3>
            <p className="text-sm">세션을 생성하거나 참가하여 모험을 시작하세요</p>
          </div>
        )}
      </div>
      
      {/* Action Input Section */}
      <div className="p-4 border-t border-slate-200 bg-white">
        <h3 className="text-xs font-bold text-slate-400 uppercase mb-2 ml-1">당신의 행동</h3>
        <div className="flex items-end gap-2">
          <div className="relative flex-1">
            <textarea
              ref={actionInputRef}
              rows={1}
              value={actionText}
              onChange={(e) => setActionText(e.target.value)}
              onKeyDown={handleActionInputKeyDown}
              placeholder={actionInputDisabled ? "운명이 펼쳐지고 있습니다..." : "행동을 설명하세요..."}
              className="w-full min-h-[48px] max-h-48 resize-none bg-slate-50 text-slate-900 px-4 py-3 rounded-lg text-sm border border-slate-200 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all placeholder:text-slate-400 disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-slate-100"
              disabled={actionInputDisabled || !currentSession || !currentCharacter}
            />
          </div>
          
          <button
            onClick={handleSubmitAction}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-3 sm:px-6 rounded-lg text-sm font-bold shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none"
            disabled={actionInputDisabled || !actionText.trim() || !currentSession || !currentCharacter}
          >
            행동
          </button>
        </div>
        
        <div className="h-5 mt-1 flex items-center justify-between px-1">
            {!actionInputDisabled && (
            <span className="text-[11px] text-slate-400">
                Enter 제출, Shift+Enter 줄바꿈
            </span>
            )}
            {actionInputDisabled && (
            <span className="text-[11px] text-yellow-600 font-medium flex items-center gap-1.5 animate-pulse">
                <span className="w-1.5 h-1.5 bg-yellow-600 rounded-full"></span>
                게임 마스터가 고민 중입니다...
            </span>
            )}
            
            {!currentCharacter && currentSession && (
            <span className="text-[11px] text-slate-400 italic">
                * 참여하려면 캐릭터를 생성하세요
            </span>
            )}
        </div>
      </div>
      
      {/* Moderation Modal */}
      <ModerationModal 
        isOpen={showModerationModal} 
        onClose={() => setShowModerationModal(false)}
        hostUserId={currentUserId ?? undefined}
      />
    </div>
  );
}
