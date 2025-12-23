import { useState, useEffect, useRef } from 'react';
import { useSocketStore } from '../stores/socketStore';
import { useGameStore } from '../stores/gameStore';
import type { JudgmentSetup, JudgmentResult } from '../types/judgment';
import DiceRollAnimation from './DiceRollAnimation';

interface JudgmentPanelProps {
  judgments: (JudgmentSetup | JudgmentResult)[];
  currentJudgmentIndex: number;
}

// NOTE: Action text is revealed to all participants during the judgment phase
// This is when actions become public after being private during submission (Requirement 2.3)

export default function JudgmentPanel({ judgments, currentJudgmentIndex }: JudgmentPanelProps) {
  const [expandedJudgments, setExpandedJudgments] = useState<Set<number>>(new Set());
  const [isHighlighted, setIsHighlighted] = useState(false);
  const emit = useSocketStore((state) => state.emit);
  const currentCharacter = useGameStore((state) => state.currentCharacter);
  const rollButtonRef = useRef<HTMLButtonElement>(null);
  const activeJudgmentRef = useRef<HTMLDivElement>(null);
  const [announcement, setAnnouncement] = useState<string>('');

  // Trigger highlight animation when currentJudgmentIndex changes
  useEffect(() => {
    if (currentJudgmentIndex > 0) {
      setIsHighlighted(true);
      const timer = setTimeout(() => {
        setIsHighlighted(false);
      }, 1500); // Animation duration: 1.5 seconds
      
      return () => clearTimeout(timer);
    }
  }, [currentJudgmentIndex]);

  // Focus management and screen reader announcements
  useEffect(() => {
    const activeJudgment = judgments[currentJudgmentIndex];
    if (!activeJudgment) return;

    // Scroll active judgment into view
    if (activeJudgmentRef.current) {
      activeJudgmentRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // Announce judgment progression to screen readers
    if (activeJudgment.status === 'active') {
      const message = `새로운 판정: ${activeJudgment.character_name}의 행동. ${activeJudgment.action_text}. 능력치 ${getAbilityLabel(activeJudgment.ability_score)} ${activeJudgment.modifier >= 0 ? '+' : ''}${activeJudgment.modifier}, 난이도 ${activeJudgment.difficulty}`;
      setAnnouncement(message);
      
      // Focus roll button if it's the current player's turn
      if (currentCharacter && activeJudgment.character_id === currentCharacter.id) {
        setTimeout(() => {
          rollButtonRef.current?.focus();
        }, 100);
      }
    } else if (activeJudgment.status === 'complete' && isJudgmentResult(activeJudgment)) {
      const message = `판정 완료: ${activeJudgment.character_name}이(가) ${activeJudgment.dice_result}를 굴렸습니다. 최종 값 ${activeJudgment.final_value}. 결과: ${getOutcomeLabel(activeJudgment.outcome)}`;
      setAnnouncement(message);
    }
  }, [currentJudgmentIndex, judgments, currentCharacter]);

  if (judgments.length === 0) {
    return null;
  }

  // CSS for pulse animation
  const pulseAnimation = isHighlighted ? {
    animation: 'judgmentPulse 1.5s ease-in-out'
  } : {};

  const activeJudgment = judgments[currentJudgmentIndex];
  const completedJudgments = judgments.slice(0, currentJudgmentIndex);
  const waitingCount = judgments.length - currentJudgmentIndex - 1;

  const handleRollDice = (actionId: number) => {
    // Get current session from gameStore
    const currentSession = useGameStore.getState().currentSession;
    
    if (!currentSession || !currentCharacter) {
      console.error('Cannot roll dice: missing session or character');
      return;
    }
    
    // Generate random d20 result (1-20)
    const diceResult = Math.floor(Math.random() * 20) + 1;
    
    // Emit roll_dice event with all required data
    emit('roll_dice', { 
      session_id: currentSession.id,
      character_id: currentCharacter.id,
      judgment_id: actionId,
      dice_result: diceResult
    });
  };

  const toggleExpanded = (actionId: number) => {
    setExpandedJudgments((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(actionId)) {
        newSet.delete(actionId);
      } else {
        newSet.add(actionId);
      }
      return newSet;
    });
  };

  const getAbilityLabel = (ability: string): string => {
    const labels: Record<string, string> = {
      str: 'STR',
      dex: 'DEX',
      con: 'CON',
      int: 'INT',
      wis: 'WIS',
      cha: 'CHA'
    };
    return labels[ability.toLowerCase()] || ability.toUpperCase();
  };

  const getOutcomeLabel = (outcome: string): string => {
    const labels: Record<string, string> = {
      critical_failure: '대실패',
      failure: '실패',
      success: '성공',
      critical_success: '대성공'
    };
    return labels[outcome] || outcome;
  };

  const getOutcomeColor = (outcome: string): string => {
    const colors: Record<string, string> = {
      critical_failure: 'bg-red-100 text-red-800 border-red-300',
      failure: 'bg-orange-100 text-orange-800 border-orange-300',
      success: 'bg-green-100 text-green-800 border-green-300',
      critical_success: 'bg-yellow-100 text-yellow-800 border-yellow-300'
    };
    return colors[outcome] || 'bg-slate-100 text-slate-800 border-slate-300';
  };

  const isJudgmentResult = (judgment: JudgmentSetup | JudgmentResult): judgment is JudgmentResult => {
    return 'dice_result' in judgment;
  };

  // Keyboard navigation handler
  const handleKeyDown = (e: React.KeyboardEvent, actionId: number) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggleExpanded(actionId);
    }
  };

  return (
    <>
      {/* Screen reader announcements */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {announcement}
      </div>

      <style>{`
        @keyframes judgmentPulse {
          0%, 100% {
            transform: scale(1);
            box-shadow: 0 0 0 0 rgba(59, 130, 246, 0);
          }
          25% {
            transform: scale(1.02);
            box-shadow: 0 0 0 8px rgba(59, 130, 246, 0.3);
          }
          50% {
            transform: scale(1);
            box-shadow: 0 0 0 12px rgba(59, 130, 246, 0.2);
          }
          75% {
            transform: scale(1.01);
            box-shadow: 0 0 0 8px rgba(59, 130, 246, 0.1);
          }
        }

        /* Mobile-optimized animations - reduce complexity on small screens */
        @media (max-width: 767px) {
          @keyframes judgmentPulse {
            0%, 100% {
              transform: scale(1);
              box-shadow: 0 0 0 0 rgba(59, 130, 246, 0);
            }
            50% {
              transform: scale(1.01);
              box-shadow: 0 0 0 6px rgba(59, 130, 246, 0.2);
            }
          }
        }

        /* Reduce motion for users who prefer it */
        @media (prefers-reduced-motion: reduce) {
          @keyframes judgmentPulse {
            0%, 100% {
              box-shadow: 0 0 0 0 rgba(59, 130, 246, 0);
            }
            50% {
              box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.3);
            }
          }
        }
      `}</style>
      <div 
        className="mb-4 md:mb-6 bg-white rounded-lg md:rounded-xl shadow-lg border border-slate-200 overflow-hidden"
        role="region"
        aria-label="판정 패널"
      >
      {/* Panel Header */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-4 py-3 md:px-6 md:py-4">
        <div className="flex items-center justify-between">
          <h3 className="text-white font-bold text-base md:text-lg" id="judgment-panel-title">판정 진행 중</h3>
          <div 
            className="bg-white/20 backdrop-blur-sm px-3 py-1 md:px-4 md:py-1.5 rounded-full"
            role="status"
            aria-label={`진행 상황: ${currentJudgmentIndex + 1}번째 판정, 총 ${judgments.length}개`}
          >
            <span className="text-white font-semibold text-xs md:text-sm" aria-hidden="true">
              {currentJudgmentIndex + 1} / {judgments.length}
            </span>
          </div>
        </div>
      </div>

      <div className="p-4 md:p-6 space-y-3 md:space-y-4">
        {/* Active Judgment - Large Prominent Card */}
        {activeJudgment && (
          <div 
            ref={activeJudgmentRef}
            className={`bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg md:rounded-xl p-3 sm:p-4 md:p-6 border-2 border-blue-300 shadow-md transition-all duration-500 ${
              isHighlighted ? 'ring-2 md:ring-4 ring-blue-400 ring-opacity-50 scale-[1.01] md:scale-[1.02]' : ''
            }`}
            style={pulseAnimation}
            role="article"
            aria-labelledby="active-judgment-character"
            aria-describedby="active-judgment-action"
          >
            {/* Character Name with Icon */}
            <div className="flex items-center gap-2 md:gap-3 mb-3 md:mb-4">
              <div 
                className="w-10 h-10 md:w-12 md:h-12 bg-blue-600 rounded-full flex items-center justify-center text-white text-base md:text-lg font-bold shadow-md flex-shrink-0"
                aria-hidden="true"
              >
                {activeJudgment.character_name.charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <h4 
                  id="active-judgment-character"
                  className="text-base sm:text-lg md:text-xl font-bold text-slate-800 truncate"
                >
                  {activeJudgment.character_name}
                </h4>
                <p className="text-xs text-slate-500 uppercase tracking-wide font-semibold" aria-label="현재 판정 중인 캐릭터">
                  현재 판정 중
                </p>
              </div>
            </div>

            {/* Action Text */}
            <div className="mb-3 md:mb-4 bg-white rounded-lg p-3 md:p-4 border border-blue-200">
              <p className="text-xs md:text-sm text-slate-600 font-semibold mb-1" id="active-judgment-action-label">행동:</p>
              <p 
                id="active-judgment-action"
                className="text-sm md:text-base text-slate-800 leading-relaxed break-words whitespace-pre-wrap"
                aria-labelledby="active-judgment-action-label"
              >
                {activeJudgment.action_text}
              </p>
            </div>

            {/* Ability Score and DC - Stacked on mobile (< 768px), side-by-side on tablet+ */}
            <div className="flex flex-col md:grid md:grid-cols-2 gap-2 sm:gap-3 md:gap-4 mb-3 md:mb-4">
              <div 
                className="bg-white rounded-lg p-3 md:p-4 border border-blue-200 text-center"
                role="group"
                aria-label={`능력치: ${getAbilityLabel(activeJudgment.ability_score)} ${activeJudgment.modifier >= 0 ? '+' : ''}${activeJudgment.modifier}`}
              >
                <p className="text-xs text-slate-500 font-semibold mb-1 uppercase" id="ability-score-label">능력치</p>
                <p className="text-xl sm:text-2xl md:text-3xl font-bold text-blue-600" aria-labelledby="ability-score-label">
                  {getAbilityLabel(activeJudgment.ability_score)}
                  <span className="text-lg sm:text-xl md:text-2xl ml-1 sm:ml-2">
                    {activeJudgment.modifier >= 0 ? '+' : ''}
                    {activeJudgment.modifier}
                  </span>
                </p>
              </div>
              <div 
                className="bg-white rounded-lg p-3 md:p-4 border border-blue-200 text-center"
                role="group"
                aria-label={`난이도: ${activeJudgment.difficulty}`}
              >
                <p className="text-xs text-slate-500 font-semibold mb-1 uppercase" id="difficulty-label">난이도</p>
                <p className="text-xl sm:text-2xl md:text-3xl font-bold text-slate-700" aria-labelledby="difficulty-label">
                  DC {activeJudgment.difficulty}
                </p>
              </div>
            </div>

            {/* Difficulty Reasoning */}
            <div className="mb-3 md:mb-4 bg-white/70 rounded-lg p-3 md:p-4 border border-blue-200">
              <p className="text-xs text-slate-600 font-semibold mb-1 sm:mb-2 uppercase" id="reasoning-label">판정 근거:</p>
              <p 
                className="text-xs md:text-sm text-slate-700 leading-relaxed italic break-words whitespace-pre-wrap"
                aria-labelledby="reasoning-label"
              >
                {activeJudgment.difficulty_reasoning}
              </p>
            </div>

            {/* Dice Roll Section */}
            {activeJudgment.status === 'rolling' && isJudgmentResult(activeJudgment) && (
              <div className="bg-white rounded-lg p-3 sm:p-4 md:p-6 border-2 border-blue-300">
                <DiceRollAnimation
                  result={activeJudgment.dice_result}
                  isCriticalSuccess={activeJudgment.dice_result === 20}
                  isCriticalFailure={activeJudgment.dice_result === 1}
                />
              </div>
            )}

            {/* Dice Result Display */}
            {activeJudgment.status === 'complete' && isJudgmentResult(activeJudgment) && (
              <div 
                className="bg-white rounded-lg p-3 sm:p-4 md:p-6 border-2 border-slate-300"
                role="status"
                aria-label={`주사위 결과: ${activeJudgment.dice_result}, 최종 값: ${activeJudgment.final_value}, ${getOutcomeLabel(activeJudgment.outcome)}`}
              >
                <div className="text-center mb-3 md:mb-4">
                  <div 
                    className="text-4xl sm:text-5xl md:text-6xl font-bold text-slate-700 mb-2"
                    aria-label={`주사위 결과 ${activeJudgment.dice_result}`}
                  >
                    {activeJudgment.dice_result}
                  </div>
                  <div className="text-xs sm:text-sm text-slate-500 mb-2 sm:mb-3">
                    최종 값: {activeJudgment.final_value} 
                    <span className="text-xs ml-1 sm:ml-2">
                      ({activeJudgment.dice_result} + {activeJudgment.modifier})
                    </span>
                  </div>
                  <div 
                    className={`inline-block px-3 py-1 sm:px-4 sm:py-1.5 md:px-6 md:py-2 rounded-full border-2 font-bold text-sm sm:text-base md:text-lg ${getOutcomeColor(activeJudgment.outcome)}`}
                    role="status"
                    aria-label={`판정 결과: ${getOutcomeLabel(activeJudgment.outcome)}`}
                  >
                    {getOutcomeLabel(activeJudgment.outcome)}
                  </div>
                </div>
                {activeJudgment.outcome_reasoning && (
                  <div className="mt-3 md:mt-4 pt-3 md:pt-4 border-t border-slate-200">
                    <p className="text-xs text-slate-600 font-semibold mb-1 sm:mb-2 uppercase" id="outcome-reasoning-label">결과:</p>
                    <p 
                      className="text-xs md:text-sm text-slate-700 leading-relaxed italic break-words whitespace-pre-wrap"
                      aria-labelledby="outcome-reasoning-label"
                    >
                      {activeJudgment.outcome_reasoning}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Next Button - Only for the player who rolled when status is 'complete' */}
            {activeJudgment.status === 'complete' && isJudgmentResult(activeJudgment) && (
              <div className="mt-3 md:mt-4">
                {currentCharacter && activeJudgment.character_id === currentCharacter.id ? (
                  currentJudgmentIndex < judgments.length - 1 ? (
                    <button
                      onClick={() => {
                        const currentSession = useGameStore.getState().currentSession;
                        if (currentSession) {
                          emit('next_judgment', {
                            session_id: currentSession.id,
                            current_index: currentJudgmentIndex
                          });
                        }
                      }}
                      className="w-full bg-gradient-to-r from-green-600 to-green-700 hover:from-green-700 hover:to-green-800 active:from-green-800 active:to-green-900 text-white font-bold py-3 px-4 sm:py-3.5 md:py-4 md:px-6 rounded-lg shadow-lg transition-all transform active:scale-95 text-sm sm:text-base md:text-lg min-h-[44px] touch-manipulation focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
                      style={{ WebkitTapHighlightColor: 'transparent' }}
                      aria-label="다음 판정으로 이동"
                    >
                      ➡️ 다음
                    </button>
                  ) : (
                    <button
                      onClick={() => {
                        const currentSession = useGameStore.getState().currentSession;
                        if (currentSession) {
                          // Trigger story generation for the last judgment
                          emit('trigger_story_generation', {
                            session_id: currentSession.id
                          });
                        }
                      }}
                      className="w-full bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 active:from-purple-800 active:to-purple-900 text-white font-bold py-3 px-4 sm:py-3.5 md:py-4 md:px-6 rounded-lg shadow-lg transition-all transform active:scale-95 text-sm sm:text-base md:text-lg min-h-[44px] touch-manipulation focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2"
                      style={{ WebkitTapHighlightColor: 'transparent' }}
                      aria-label="모든 판정 완료. 이야기 생성 시작"
                    >
                      ✨ 이야기 진행
                    </button>
                  )
                ) : (
                  <div 
                    className="w-full bg-slate-100 text-slate-500 font-semibold py-3 px-4 sm:py-3.5 md:py-4 md:px-6 rounded-lg text-center border-2 border-dashed border-slate-300 min-h-[44px] flex items-center justify-center text-sm sm:text-base"
                    role="status"
                    aria-label={`${activeJudgment.character_name}이(가) 다음 버튼을 누를 때까지 대기 중`}
                  >
                    대기 중...
                  </div>
                )}
              </div>
            )}

            {/* Roll Button - Only for action owner when status is 'active' */}
            {activeJudgment.status === 'active' && (
              <div className="mt-3 md:mt-4">
                {currentCharacter && activeJudgment.character_id === currentCharacter.id ? (
                  <button
                    ref={rollButtonRef}
                    onClick={() => handleRollDice(activeJudgment.action_id)}
                    className="w-full bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 active:from-blue-800 active:to-blue-900 text-white font-bold py-3 px-4 sm:py-3.5 md:py-4 md:px-6 rounded-lg shadow-lg transition-all transform active:scale-95 text-sm sm:text-base md:text-lg min-h-[44px] touch-manipulation focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                    style={{ WebkitTapHighlightColor: 'transparent' }}
                    aria-label={`${activeJudgment.character_name}의 행동에 대해 주사위 굴리기. 능력치 ${getAbilityLabel(activeJudgment.ability_score)} ${activeJudgment.modifier >= 0 ? '+' : ''}${activeJudgment.modifier}, 난이도 ${activeJudgment.difficulty}`}
                    aria-describedby="active-judgment-action"
                  >
                    🎲 주사위 굴리기
                  </button>
                ) : (
                  <div 
                    className="w-full bg-slate-100 text-slate-500 font-semibold py-3 px-4 sm:py-3.5 md:py-4 md:px-6 rounded-lg text-center border-2 border-dashed border-slate-300 min-h-[44px] flex items-center justify-center text-sm sm:text-base"
                    role="status"
                    aria-label={`${activeJudgment.character_name}이(가) 주사위를 굴릴 차례입니다. 대기 중`}
                  >
                    대기 중...
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Completed Judgments - Collapsed Summary */}
        {completedJudgments.length > 0 && (
          <div className="space-y-2" role="region" aria-label="완료된 판정 목록">
            <h4 
              className="text-xs sm:text-sm font-semibold text-slate-600 uppercase tracking-wide px-1 sm:px-2"
              id="completed-judgments-heading"
            >
              완료된 판정
            </h4>
            {completedJudgments.map((judgment) => {
              const isExpanded = expandedJudgments.has(judgment.action_id);
              const result = isJudgmentResult(judgment) ? judgment : null;

              return (
                <div
                  key={judgment.action_id}
                  className="bg-slate-50 rounded-lg border border-slate-200 overflow-hidden transition-all hover:shadow-md"
                >
                  {/* Collapsed Summary */}
                  <button
                    onClick={() => toggleExpanded(judgment.action_id)}
                    onKeyDown={(e) => handleKeyDown(e, judgment.action_id)}
                    className="w-full px-3 py-2.5 sm:px-4 sm:py-3 flex items-center justify-between hover:bg-slate-100 transition-colors touch-manipulation min-h-[44px] focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset"
                    style={{ WebkitTapHighlightColor: 'transparent' }}
                    aria-expanded={isExpanded}
                    aria-controls={`judgment-details-${judgment.action_id}`}
                    aria-label={`${judgment.character_name}의 판정. ${result ? `주사위 ${result.dice_result}, 최종 값 ${result.final_value}, ${getOutcomeLabel(result.outcome)}` : ''}. ${isExpanded ? '접기' : '펼치기'}`}
                  >
                    <div className="flex items-center gap-2 sm:gap-3 min-w-0 flex-1">
                      <div className="w-8 h-8 bg-slate-400 rounded-full flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
                        {judgment.character_name.charAt(0).toUpperCase()}
                      </div>
                      <div className="text-left min-w-0 flex-1">
                        <p className="font-semibold text-slate-800 text-xs sm:text-sm truncate">
                          {judgment.character_name}
                        </p>
                        {result && (
                          <p className="text-xs text-slate-500">
                            주사위: {result.dice_result} (최종: {result.final_value})
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
                      {result && (
                        <span className={`hidden sm:inline-block px-2 sm:px-3 py-0.5 sm:py-1 rounded-full text-xs font-bold border ${getOutcomeColor(result.outcome)}`}>
                          {getOutcomeLabel(result.outcome)}
                        </span>
                      )}
                      {result && (
                        <span className={`sm:hidden w-6 h-6 rounded-full border-2 flex items-center justify-center text-xs font-bold ${getOutcomeColor(result.outcome)}`}>
                          {result.outcome === 'critical_success' ? '★' : result.outcome === 'success' ? '✓' : result.outcome === 'critical_failure' ? '✗' : '−'}
                        </span>
                      )}
                      <svg
                        className={`w-4 h-4 sm:w-5 sm:h-5 text-slate-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </button>

                  {/* Expanded Details */}
                  {isExpanded && (
                    <div 
                      id={`judgment-details-${judgment.action_id}`}
                      className="px-3 pb-3 pt-2 sm:px-4 sm:pb-4 border-t border-slate-200 bg-white space-y-2 sm:space-y-3"
                      role="region"
                      aria-label={`${judgment.character_name} 판정 상세 정보`}
                    >
                      <div>
                        <p className="text-xs text-slate-500 font-semibold mb-1" id={`action-label-${judgment.action_id}`}>행동:</p>
                        <p 
                          className="text-xs sm:text-sm text-slate-700 break-words whitespace-pre-wrap"
                          aria-labelledby={`action-label-${judgment.action_id}`}
                        >
                          {judgment.action_text}
                        </p>
                      </div>
                      <div className="grid grid-cols-2 gap-2 sm:gap-3">
                        <div>
                          <p className="text-xs text-slate-500 font-semibold mb-1" id={`ability-label-${judgment.action_id}`}>능력치:</p>
                          <p 
                            className="text-xs sm:text-sm font-bold text-slate-700"
                            aria-labelledby={`ability-label-${judgment.action_id}`}
                          >
                            {getAbilityLabel(judgment.ability_score)} {judgment.modifier >= 0 ? '+' : ''}{judgment.modifier}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500 font-semibold mb-1" id={`dc-label-${judgment.action_id}`}>난이도:</p>
                          <p 
                            className="text-xs sm:text-sm font-bold text-slate-700"
                            aria-labelledby={`dc-label-${judgment.action_id}`}
                          >
                            DC {judgment.difficulty}
                          </p>
                        </div>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500 font-semibold mb-1" id={`reasoning-label-${judgment.action_id}`}>판정 근거:</p>
                        <p 
                          className="text-xs sm:text-sm text-slate-600 italic break-words whitespace-pre-wrap"
                          aria-labelledby={`reasoning-label-${judgment.action_id}`}
                        >
                          {judgment.difficulty_reasoning}
                        </p>
                      </div>
                      {result && result.outcome_reasoning && (
                        <div>
                          <p className="text-xs text-slate-500 font-semibold mb-1" id={`outcome-label-${judgment.action_id}`}>결과:</p>
                          <p 
                            className="text-xs sm:text-sm text-slate-600 italic break-words whitespace-pre-wrap"
                            aria-labelledby={`outcome-label-${judgment.action_id}`}
                          >
                            {result.outcome_reasoning}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Waiting Judgments Count */}
        {waitingCount > 0 && (
          <div 
            className="bg-slate-50 rounded-lg px-3 py-2.5 sm:px-4 sm:py-3 border border-slate-200 text-center"
            role="status"
            aria-label={`대기 중인 판정 ${waitingCount}개`}
          >
            <p className="text-xs sm:text-sm text-slate-600">
              <span className="font-semibold">대기 중인 판정:</span>{' '}
              <span className="font-bold text-slate-800">{waitingCount}개</span>
            </p>
          </div>
        )}
      </div>
    </div>
    </>
  );
}
