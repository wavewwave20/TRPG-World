import { useState, useEffect, useRef } from 'react';
import { useGameStore } from '../stores/gameStore';
import { useSocketStore } from '../stores/socketStore';
import { useActionStore } from '../stores/actionStore';
import { useStoryStore } from '../stores/storyStore';
import { useAuthStore } from '../stores/authStore';
import { useChatStore } from '../stores/chatStore';
import { useAIStore } from '../stores/aiStore';
import { getStoryLogs } from '../services/api';
// SessionCreationForm removed from in-session view
import ModerationModal from './ModerationModal';
import TypingText from './TypingText';
// import AIGenerationIndicator from './AIGenerationIndicator'; // REMOVED for streaming optimization
import JudgmentResultsButton from './JudgmentResultsButton';
import type { JudgmentSummary } from '../services/api';

export default function CenterPane() {
  const [actionText, setActionText] = useState('');
  const [showModerationModal, setShowModerationModal] = useState(false);
  
  const currentSession = useGameStore((state) => state.currentSession);
  const currentCharacter = useGameStore((state) => state.currentCharacter);
  const setSession = useGameStore((state) => state.setSession);
  const setJudgmentModalOpen = useGameStore((state) => state.setJudgmentModalOpen);
  const emit = useSocketStore((state) => state.emit);
  const clearChat = useChatStore((state) => state.clear);
  
  const actionInputDisabled = useActionStore((state) => state.actionInputDisabled);
  const setActionInputDisabled = useActionStore((state) => state.setActionInputDisabled);
  const queueCount = useActionStore((state) => state.queueCount);
  
  const entries = useStoryStore((state) => state.entries);
  const setEntries = useStoryStore((state) => state.setEntries);
  
  const currentUserId = useAuthStore((state) => state.userId);
  
  const isGenerating = useAIStore((state) => state.isGenerating);
  const judgments = useAIStore((state) => state.judgments);
  const currentNarrative = useAIStore((state) => state.currentNarrative);
  
  const storyEndRef = useRef<HTMLDivElement>(null);
  const actionInputRef = useRef<HTMLInputElement>(null);
  const narrativeEndRef = useRef<HTMLDivElement>(null);
  
  // Check if current user is host
  const isHost = currentSession?.hostUserId === currentUserId;

  // Load story logs on session change using getStoryLogs API
  useEffect(() => {
    if (currentSession) {
      getStoryLogs(currentSession.id)
        .then((data) => {
          setEntries(data.logs);
        })
        .catch((error) => {
          console.error('Failed to load story logs:', error);
        });
    }
  }, [currentSession, setEntries]);

  // Reload story logs when narrative streaming completes
  const skipNextScrollRef = useRef<boolean>(false);
  useEffect(() => {
    const handleStoryLogsUpdated = (event: CustomEvent<{ session_id: number }>) => {
      if (currentSession && event.detail.session_id === currentSession.id) {
        // Skip scroll when reloading after narrative complete
        skipNextScrollRef.current = true;
        getStoryLogs(currentSession.id)
          .then((data) => {
            setEntries(data.logs);
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
  }, [currentSession, setEntries]);

  // Auto-scroll to latest entry when entries change (skip after narrative complete)
  useEffect(() => {
    if (skipNextScrollRef.current) {
      skipNextScrollRef.current = false;
      return;
    }
    storyEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries]);

  // Scroll to narrative start only once when streaming begins
  const hasScrolledToNarrativeRef = useRef<boolean>(false);
  useEffect(() => {
    // Reset scroll flag when narrative is cleared
    if (!currentNarrative) {
      hasScrolledToNarrativeRef.current = false;
      return;
    }
    
    // Scroll only once when narrative first appears
    if (currentNarrative && !hasScrolledToNarrativeRef.current && narrativeEndRef.current) {
      hasScrolledToNarrativeRef.current = true;
      narrativeEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [currentNarrative]);

  // Ensure the latest USER message shows a judgment button during/after rolls
  // If backend hasn't attached judgments to the story log yet, mirror
  // the in‑memory AI judgments onto the latest USER entry so the UI can render the button.
  useEffect(() => {
    if (!entries || entries.length === 0) return;
    if (!judgments || judgments.length === 0) return;

    // Find the last USER entry
    let lastUserIndex = -1;
    for (let i = entries.length - 1; i >= 0; i--) {
      if (entries[i].role === 'USER') { lastUserIndex = i; break; }
    }
    if (lastUserIndex === -1) return;

    const target = entries[lastUserIndex];

    // Map in‑memory judgments to JudgmentSummary shape for display
    const mapped: JudgmentSummary[] = judgments.map((j: any) => ({
      // Use negative IDs to mark ephemeral mapped judgments (not from backend)
      id: j.action_id ? -Math.abs(j.action_id) : -Math.floor(Math.random() * 1_000_000) - 1,
      character_id: j.character_id,
      character_name: j.character_name,
      action_text: j.action_text,
      action_type: (j as any).action_type ?? null,
      dice_result: (j as any).dice_result ?? null,
      modifier: j.modifier ?? 0,
      final_value: (j as any).final_value ?? null,
      difficulty: j.difficulty,
      outcome: (j as any).outcome ?? null,
    }));

    // Decide whether to write/refresh judgments on the target entry
    const hasBackendJudgments = !!(target.judgments && target.judgments.length > 0 && target.judgments.every(j => j.id > 0));

    // If backend already attached real judgments, do not overwrite
    if (hasBackendJudgments) return;

    const needsUpdate = (() => {
      if (!target.judgments || target.judgments.length === 0) return true;
      if (target.judgments.length !== mapped.length) return true;
      // If any field differs, refresh
      for (let i = 0; i < mapped.length; i++) {
        const a = mapped[i];
        const b = target.judgments[i] as any;
        if (
          a.character_id !== b.character_id ||
          a.character_name !== b.character_name ||
          a.action_text !== b.action_text ||
          a.difficulty !== b.difficulty ||
          a.modifier !== b.modifier ||
          a.dice_result !== b.dice_result ||
          a.final_value !== b.final_value ||
          a.outcome !== b.outcome
        ) {
          return true;
        }
      }
      return false;
    })();

    if (!needsUpdate) return;

    const next = entries.slice();
    next[lastUserIndex] = { ...target, judgments: mapped } as any;
    setEntries(next);
  }, [entries, judgments, setEntries]);

  // Listen for story_committed event to re-enable input
  useEffect(() => {
    const socket = useSocketStore.getState().socket;
    
    if (!socket) return;
    
    const handleStoryCommitted = () => {
      // Clear action input text
      setActionText('');
      
      // Focus input field
      actionInputRef.current?.focus();
    };
    const handleSessionEnded = (data: { session_id: number; reason?: string }) => {
      if (!currentSession) return;
      if (data.session_id !== currentSession.id) return;
      // Clear state and return to lobby
      clearChat();
      setSession(null);
      setActionInputDisabled(false);
    };
    
    socket.on('story_committed', handleStoryCommitted);
    socket.on('session_ended', handleSessionEnded);
    
    // Cleanup listener on unmount
    return () => {
      socket.off('story_committed', handleStoryCommitted);
      socket.off('session_ended', handleSessionEnded);
    };
  }, [currentSession, clearChat, setSession, setActionInputDisabled]);

  // Leaving handled via App header back button

  const handleSubmitAction = () => {
    // Validate action text is non-empty
    if (!actionText.trim()) {
      return;
    }
    
    // Ensure we have session and character
    if (!currentSession || !currentCharacter) {
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

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSubmitAction();
    }
  };

  return (
    <div className="h-full flex flex-col relative z-10 bg-white">
      <div className="flex justify-between items-center px-6 py-4 border-b border-slate-200 bg-white sticky top-0 z-20">
        <h2 className="text-lg font-bold text-slate-800">
          스토리북
        </h2>
        
        {/* Session Info or Create Button */}
        {currentSession ? (
          <div className="flex items-center gap-3">
            {/* Moderation Button - Only show when user is host */}
            {isHost && (
              <button
                onClick={() => setShowModerationModal(true)}
                className="relative bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 px-3 py-1.5 rounded-lg text-xs font-semibold shadow-sm transition-all hover:border-slate-300"
              >
                행동 결정
                {/* Queue count badge - Show when queueCount > 0 */}
                {queueCount > 0 && (
                  <span className="absolute -top-2 -right-2 bg-red-500 text-white text-[10px] font-bold rounded-full h-5 w-5 flex items-center justify-center shadow-sm border border-white">
                    {queueCount}
                  </span>
                )}
              </button>
            )}
          </div>
        ) : (
          <div />
        )}
      </div>
      
      {/* Session Creation Form removed from in-session view */}
      
      {/* Story Content Section */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 scroll-smooth bg-slate-50/50 relative">
        {/* AI Generation Indicator - REMOVED for streaming optimization */}
        {/* <AIGenerationIndicator isGenerating={isGenerating} /> */}
        
        {currentSession ? (
          <>
            {entries.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-slate-400 text-center">
                <div className="text-4xl mb-3">📜</div>
                <p>스토리북이 비어있습니다. 당신의 모험이 쓰여지길 기다립니다...</p>
              </div>
            ) : (
              entries.map((entry, index) => {
                const isNewestEntry = index === entries.length - 1;
                
                // Debug log for ALL messages to see what data we have
                console.log(`📝 ${entry.role} Message:`, {
                  id: entry.id,
                  role: entry.role,
                  hasJudgments: !!entry.judgments,
                  judgmentCount: entry.judgments?.length || 0,
                  judgments: entry.judgments
                });
                
                // Check if button should render
                const shouldShowButton = entry.role === 'USER' && entry.judgments && entry.judgments.length > 0;
                if (entry.role === 'USER') {
                  console.log(`🔍 USER Message button check:`, {
                    id: entry.id,
                    shouldShowButton,
                    hasJudgments: !!entry.judgments,
                    judgmentCount: entry.judgments?.length || 0
                  });
                }
                
                // Determine if reopen modal button should be shown for this entry
                const entryJudgments = entry.judgments ?? [];
                const allCompleteForEntry = entryJudgments.length > 0 && entryJudgments.every((j: any) => j.dice_result !== null && j.outcome !== null);
                const myCompletedForEntry = currentCharacter ? entryJudgments.some((j: any) => j.character_id === currentCharacter.id && j.dice_result !== null && j.outcome !== null) : false;
                const showOpenModal = !allCompleteForEntry && !myCompletedForEntry;

                return (
                  <div
                    key={entry.id}
                    className={`flex flex-col max-w-3xl ${
                      entry.role === 'USER' ? 'ml-auto items-end' : 'mr-auto items-start'
                    }`}
                  >
                    <div className={`text-[10px] font-bold uppercase tracking-wider mb-1 px-1 ${
                      entry.role === 'USER' ? 'text-blue-600' : 'text-slate-500'
                    }`}>
                      {entry.role === 'USER' ? '모험가들' : '던전 마스터'}
                    </div>
                    
                    <div
                      className={`px-6 py-4 rounded-2xl shadow-sm text-sm leading-relaxed whitespace-pre-wrap max-w-full ${
                        entry.role === 'USER' 
                          ? 'bg-blue-50 text-slate-800 border border-blue-100 rounded-tr-none' 
                          : 'bg-white text-slate-700 border border-slate-200 rounded-tl-none font-serif'
                      }`}
                    >
                      {entry.content}
                      
                      {/* Show judgment results button for USER messages with judgments */}
                      {entry.role === 'USER' && entry.judgments && entry.judgments.length > 0 && (
                        <JudgmentResultsButton 
                          judgments={entry.judgments}
                          onOpenModal={showOpenModal ? () => setJudgmentModalOpen(true) : undefined}
                        />
                      )}
                    </div>
                  </div>
                );
              })
            )}
            
            {/* Streaming Narrative - show at the bottom when narrative is being generated */}
            {currentNarrative && (
              <div className="flex flex-col max-w-3xl mr-auto items-start">
                <div className="text-[10px] font-bold uppercase tracking-wider mb-1 px-1 text-slate-500">
                  던전 마스터
                </div>
                <div className="px-6 py-4 rounded-2xl shadow-sm text-sm leading-relaxed whitespace-pre-wrap max-w-full bg-white text-slate-700 border border-slate-200 rounded-tl-none font-serif">
                  <span>{currentNarrative}</span>
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
        <div className="flex gap-2">
          <div className="relative flex-1">
            <input
              ref={actionInputRef}
              type="text"
              value={actionText}
              onChange={(e) => setActionText(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={actionInputDisabled ? "운명이 펼쳐지고 있습니다..." : "행동을 설명하세요..."}
              className="w-full bg-slate-50 text-slate-900 px-4 py-3 rounded-lg text-sm border border-slate-200 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all placeholder:text-slate-400 disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-slate-100"
              disabled={actionInputDisabled || !currentSession || !currentCharacter}
            />
          </div>
          
          <button
            onClick={handleSubmitAction}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg text-sm font-bold shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none"
            disabled={actionInputDisabled || !actionText.trim() || !currentSession || !currentCharacter}
          >
            행동
          </button>
        </div>
        
        <div className="h-5 mt-1 flex items-center justify-between px-1">
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
