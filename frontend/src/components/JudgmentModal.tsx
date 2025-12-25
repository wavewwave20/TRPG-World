import { useEffect, useRef, useState, useCallback, useMemo, memo } from 'react';
import { FocusTrap } from 'focus-trap-react';
import Portal from './Portal';
import JudgmentModalHeader from './JudgmentModalHeader';
import ActiveJudgmentCard from './ActiveJudgmentCard';
import CompletedJudgmentsList from './CompletedJudgmentsList';
import WaitingIndicator from './WaitingIndicator';
import { useAIStore } from '../stores/aiStore';
import { useGameStore } from '../stores/gameStore';
import { useSocketStore } from '../stores/socketStore';
import type { JudgmentResult, JudgmentSetup } from '../types/judgment';
import './JudgmentModal.css';

interface JudgmentModalProps {
  /** Whether the modal is currently open */
  isOpen: boolean;
  /** Callback function to close the modal */
  onClose: () => void;
  /** Current session ID */
  sessionId: number;
}

/**
 * JudgmentModal - Main modal component for displaying judgment process
 */
function JudgmentModal({ isOpen, onClose, sessionId }: JudgmentModalProps) {
  // All hooks must be called unconditionally at the top
  const judgments = useAIStore((state) => state.judgments);
  const currentJudgmentIndex = useAIStore((state) => state.currentJudgmentIndex);
  const { emit } = useSocketStore();
  const modalContentRef = useRef<HTMLDivElement>(null);
  
  // Animation state management
  const [isClosing, setIsClosing] = useState(false);
  const [shouldRender, setShouldRender] = useState(false);
  const [judgmentTransition, setJudgmentTransition] = useState<'enter' | 'exit' | null>(null);
  const prevJudgmentIndexRef = useRef(currentJudgmentIndex);

  // Get current judgment safely
  const currentJudgment = judgments[currentJudgmentIndex] ?? null;
  const currentCharacter = useGameStore((state) => state.currentCharacter);
  const isCurrentPlayer = !!(currentJudgment && currentCharacter && currentJudgment.character_id === currentCharacter.id);

  // Memoize canClose calculation
  const canClose = useMemo(() => {
    return judgments.length > 0 && judgments.every(
      (judgment) => judgment.status === 'complete'
    );
  }, [judgments]);

  // Memoize computed values
  const isLastJudgment = useMemo(() => {
    return currentJudgmentIndex === judgments.length - 1;
  }, [currentJudgmentIndex, judgments.length]);
  
  // Memoize completed judgments array
  const completedJudgments = useMemo(() => {
    return judgments
      .slice(0, currentJudgmentIndex)
      .filter((j): j is JudgmentResult => j.status === 'complete' && 'dice_result' in j);
  }, [judgments, currentJudgmentIndex]);
  
  // Memoize waiting judgments array
  const waitingJudgments = useMemo(() => {
    return judgments
      .slice(currentJudgmentIndex + 1)
      .filter((j): j is JudgmentSetup => j.status === 'waiting' || j.status === 'active');
  }, [judgments, currentJudgmentIndex]);

  // Memoize handler functions
  const handleRollDice = useCallback((actionId: number) => {
    if (!currentJudgment) {
      console.error('❌ No current judgment available');
      return;
    }
    
    // Roll dice locally (1-20)
    const diceResult = Math.floor(Math.random() * 20) + 1;
    
    console.log('🎲 JudgmentModal: handleRollDice called', { 
      actionId, 
      characterId: currentJudgment.character_id,
      diceResult 
    });
    
    const payload = {
      session_id: sessionId,
      character_id: currentJudgment.character_id,
      judgment_id: actionId,
      dice_result: diceResult
    };
    
    console.log('🔌 Socket emit:', 'roll_dice', payload);
    emit('roll_dice', payload);
  }, [emit, currentJudgment, sessionId]);

  const handleNext = useCallback(() => {
    const state = useAIStore.getState();
    const pending = state.pendingNextIndex;
    if (pending !== null) {
      // Apply the pending transition (server already advanced); just catch up locally
      state.setCurrentJudgmentIndex(pending);
      // Update statuses accordingly
      const updated = state.judgments.map((j, idx) => {
        if (idx < pending) return { ...j, status: 'complete' as const };
        if (idx === pending) return { ...j, status: 'active' as const };
        return { ...j, status: 'waiting' as const };
      });
      useAIStore.setState({ judgments: updated, pendingNextIndex: null, ackRequiredForActionId: null });
    } else {
      // Ask server to move next (fallback if server hasn't advanced yet)
      if (currentJudgment) {
        emit('next_judgment', { session_id: sessionId, current_index: currentJudgmentIndex });
        try { useAIStore.getState().setAckRequired(null); } catch {}
      }
    }
  }, [emit, currentJudgment, currentJudgmentIndex, sessionId]);

  const handleTriggerStory = useCallback(() => {
    // **NEW: Request narrative stream (optimized flow)**
    emit('request_narrative_stream', { session_id: sessionId });
  }, [emit, sessionId]);

  const handleOverlayClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
  }, []);

  const handleContentClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
  }, []);

  // Memoize screen reader announcements
  const judgmentAnnouncement = useMemo(() => {
    if (!currentJudgment) return '';
    
    const characterName = currentJudgment.character_name;
    const status = currentJudgment.status;
    
    if (status === 'active') {
      return `${characterName}의 판정 차례입니다. 주사위를 굴려주세요.`;
    } else if (status === 'rolling') {
      return `${characterName}이(가) 주사위를 굴리는 중입니다...`;
    } else if (status === 'complete' && 'dice_result' in currentJudgment) {
      const result = currentJudgment as JudgmentResult;
      const outcomeText = result.outcome === 'critical_success' ? '대성공' :
                         result.outcome === 'success' ? '성공' :
                         result.outcome === 'failure' ? '실패' : '대실패';
      return `${characterName}의 판정 결과: 주사위 ${result.dice_result}, 최종 값 ${result.final_value}, ${outcomeText}`;
    }
    return '';
  }, [currentJudgment]);

  const progressAnnouncement = useMemo(() => {
    return `판정 진행 상황: ${currentJudgmentIndex + 1}번째 판정, 총 ${judgments.length}개 중`;
  }, [currentJudgmentIndex, judgments.length]);

  // Handle modal visibility with animation
  useEffect(() => {
    if (isOpen && judgments.length > 0) {
      setShouldRender(true);
      setIsClosing(false);
    } else if (!isOpen && shouldRender) {
      setIsClosing(true);
      const timer = setTimeout(() => {
        setShouldRender(false);
        setIsClosing(false);
      }, 200);
      return () => clearTimeout(timer);
    }
  }, [isOpen, shouldRender, judgments.length]);

  // Handle judgment transition animations
  useEffect(() => {
    if (currentJudgmentIndex !== prevJudgmentIndexRef.current && shouldRender) {
      setJudgmentTransition('exit');
      const exitTimer = setTimeout(() => {
        setJudgmentTransition('enter');
        prevJudgmentIndexRef.current = currentJudgmentIndex;
        const enterTimer = setTimeout(() => {
          setJudgmentTransition(null);
        }, 300);
        return () => clearTimeout(enterTimer);
      }, 300);
      return () => clearTimeout(exitTimer);
    }
  }, [currentJudgmentIndex, shouldRender]);

  // ESC key handler
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && canClose) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose, canClose]);

  // Body scroll lock
  useEffect(() => {
    if (isOpen) {
      const originalOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = originalOverflow;
      };
    }
  }, [isOpen]);

  // Focus management
  useEffect(() => {
    if (isOpen && modalContentRef.current) {
      const timer = setTimeout(() => {
        const focusableElements = modalContentRef.current?.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusableElements && focusableElements.length > 0) {
          (focusableElements[0] as HTMLElement).focus();
        }
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  // Early return AFTER all hooks
  if (!shouldRender || judgments.length === 0 || !currentJudgment) {
    return null;
  }

  // Determine animation classes
  const overlayClasses = `fixed inset-0 bg-black/50 backdrop-blur-sm z-[1000] judgment-modal-overlay ${
    isClosing ? 'closing' : ''
  } ${!isClosing ? 'animate-fadeIn' : ''}`;
  
  const contentClasses = `bg-white rounded-xl shadow-2xl w-full max-h-[90vh] overflow-y-auto judgment-modal-content ${
    isClosing ? 'closing' : ''
  } ${!isClosing ? 'animate-scaleIn' : ''}`;
  
  const judgmentCardClasses = judgmentTransition === 'enter' 
    ? 'judgment-card-enter' 
    : judgmentTransition === 'exit' 
    ? 'judgment-card-exit' 
    : '';

  return (
    <Portal>
      {/* Screen Reader Live Region */}
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {judgmentAnnouncement}
      </div>
      
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {progressAnnouncement}
      </div>

      <div
        className={overlayClasses}
        onClick={handleOverlayClick}
        aria-hidden="true"
      />

      <div
        className="fixed inset-0 flex items-center justify-center z-[1001] p-4"
        onClick={handleOverlayClick}
      >
        <FocusTrap
          focusTrapOptions={{
            initialFocus: false,
            allowOutsideClick: true,
            escapeDeactivates: false,
            returnFocusOnDeactivate: true,
          }}
        >
          <div
            ref={modalContentRef}
            className={contentClasses}
            onClick={handleContentClick}
            role="dialog"
            aria-modal="true"
            aria-labelledby="judgment-modal-title"
            aria-describedby="judgment-modal-description"
          >
            <JudgmentModalHeader
              currentIndex={currentJudgmentIndex}
              totalCount={judgments.length}
              onClose={onClose}
            />

            <div className="p-4 sm:p-6 space-y-4">
              <div className={judgmentCardClasses}>
                <ActiveJudgmentCard
                  judgment={currentJudgment}
                  isCurrentPlayer={isCurrentPlayer}
                  onRollDice={handleRollDice}
                  onNext={handleNext}
                  onTriggerStory={handleTriggerStory}
                  isLastJudgment={isLastJudgment}
                />
              </div>
              
              {waitingJudgments.length > 0 && (
                <WaitingIndicator waitingJudgments={waitingJudgments} />
              )}
              
              {completedJudgments.length > 0 && (
                <CompletedJudgmentsList judgments={completedJudgments} />
              )}
            </div>
          </div>
        </FocusTrap>
      </div>
    </Portal>
  );
}

export default memo(JudgmentModal);
