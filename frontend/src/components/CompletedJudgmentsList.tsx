import { useState, useCallback, memo } from 'react';
import type { JudgmentResult } from '../types/judgment';

interface CompletedJudgmentsListProps {
  /** Array of completed judgments to display */
  judgments: JudgmentResult[];
}

/**
 * CompletedJudgmentsList - Displays a list of completed judgments
 * 
 * This component shows all completed judgments in a collapsed form,
 * allowing users to expand individual items to see full details.
 * 
 * Features:
 * - Collapsed view showing character name and outcome
 * - Click to expand/collapse individual judgments
 * - Keyboard navigation support (Enter, Space)
 * - Full details when expanded (action, ability, dice result)
 * - Color-coded outcomes (success/failure)
 * - Responsive design
 * - Performance optimized with React.memo and useCallback
 * 
 * Requirements:
 * - 4.3: Display completed judgments in collapsed form at bottom of modal
 * - 4.4: Expand judgment details when clicked
 * - 6.4: Support keyboard navigation (Tab, Enter, Space)
 * - 10.1: Prevent unnecessary re-renders with React.memo
 * - 10.4: Memoize callbacks
 * 
 * @param props - Component props
 * @returns Completed judgments list component
 */
function CompletedJudgmentsList({ judgments }: CompletedJudgmentsListProps) {
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  if (judgments.length === 0) {
    return null;
  }

  // Memoize toggle function to prevent re-creating on every render
  const toggleExpanded = useCallback((actionId: number) => {
    setExpandedIds(prev => {
      const next = new Set(prev);
      if (next.has(actionId)) {
        next.delete(actionId);
      } else {
        next.add(actionId);
      }
      return next;
    });
  }, []);

  // Memoize keyboard handler to prevent re-creating on every render
  const handleKeyDown = useCallback((e: React.KeyboardEvent, actionId: number) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggleExpanded(actionId);
    }
  }, [toggleExpanded]);

  const getOutcomeColor = (outcome: string) => {
    switch (outcome) {
      case 'critical_success':
        return 'text-green-700 bg-green-50 border-green-300';
      case 'success':
        return 'text-green-600 bg-green-50 border-green-200';
      case 'failure':
        return 'text-red-600 bg-red-50 border-red-200';
      case 'critical_failure':
        return 'text-red-700 bg-red-50 border-red-300';
      default:
        return 'text-slate-600 bg-slate-50 border-slate-200';
    }
  };

  const getOutcomeIcon = (outcome: string) => {
    switch (outcome) {
      case 'critical_success':
        return '🌟';
      case 'success':
        return '✅';
      case 'failure':
        return '❌';
      case 'critical_failure':
        return '💥';
      default:
        return '⚪';
    }
  };

  const getOutcomeText = (outcome: string) => {
    switch (outcome) {
      case 'critical_success':
        return '대성공';
      case 'success':
        return '성공';
      case 'failure':
        return '실패';
      case 'critical_failure':
        return '대실패';
      default:
        return outcome;
    }
  };

  const getAbilityName = (ability: string): string => {
    const abilityNames: Record<string, string> = {
      str: '근력',
      dex: '민첩',
      con: '건강',
      int: '지능',
      wis: '지혜',
      cha: '매력'
    };
    return abilityNames[ability] || ability.toUpperCase();
  };

  return (
    <div className="space-y-2" role="region" aria-label="완료된 판정 목록">
      <h4 
        className="text-xs sm:text-sm font-semibold text-slate-600 uppercase tracking-wide"
        id="completed-judgments-heading"
      >
        완료된 판정 ({judgments.length})
      </h4>
      
      <div 
        className="space-y-2"
        role="list"
        aria-labelledby="completed-judgments-heading"
      >
        {judgments.map((judgment) => {
          const isExpanded = expandedIds.has(judgment.action_id);
          const outcomeColor = getOutcomeColor(judgment.outcome);
          
          return (
            <div
              key={judgment.action_id}
              className={`border-2 rounded-lg transition-all duration-200 ${outcomeColor}`}
              role="listitem"
            >
              {/* Collapsed Header - Always Visible */}
              <button
                onClick={() => toggleExpanded(judgment.action_id)}
                onKeyDown={(e) => handleKeyDown(e, judgment.action_id)}
                className="w-full px-3 py-2 sm:px-4 sm:py-3 flex items-center justify-between gap-2 hover:opacity-80 transition-opacity focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 rounded-lg"
                aria-expanded={isExpanded}
                aria-controls={`judgment-details-${judgment.action_id}`}
                aria-label={`${judgment.character_name}의 판정 결과: ${getOutcomeText(judgment.outcome)}. 주사위 ${judgment.dice_result}, 최종 값 ${judgment.final_value}. ${isExpanded ? '상세 정보 접기' : '상세 정보 펼치기'}`}
              >
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  {/* Character Avatar */}
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-slate-400 to-slate-600 flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
                    {judgment.character_name.charAt(0).toUpperCase()}
                  </div>
                  
                  {/* Character Name */}
                  <span className="font-semibold text-sm sm:text-base truncate">
                    {judgment.character_name}
                  </span>
                  
                  {/* Outcome Badge */}
                  <span className="text-xs sm:text-sm font-bold flex items-center gap-1 flex-shrink-0">
                    <span>{getOutcomeIcon(judgment.outcome)}</span>
                    <span className="hidden sm:inline">{getOutcomeText(judgment.outcome)}</span>
                  </span>
                </div>
                
                {/* Expand/Collapse Icon */}
                <svg
                  className={`w-5 h-5 transition-transform duration-200 flex-shrink-0 ${isExpanded ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {/* Expanded Details */}
              {isExpanded && (
                <div 
                  id={`judgment-details-${judgment.action_id}`}
                  className="px-3 pb-3 sm:px-4 sm:pb-4 space-y-3 border-t-2 border-current/20 pt-3"
                  role="region"
                  aria-label={`${judgment.character_name}의 판정 상세 정보`}
                >
                  {/* Action Text */}
                  <div>
                    <div className="text-xs font-semibold text-slate-600 mb-1">
                      행동
                    </div>
                    <p className="text-sm text-slate-700 leading-relaxed">
                      {judgment.action_text}
                    </p>
                  </div>

                  {/* Stats Grid */}
                  <div className="grid grid-cols-2 gap-2">
                    {/* Ability Score */}
                    <div 
                      className="bg-white/50 rounded p-2"
                      role="group"
                      aria-label={`능력치: ${getAbilityName(judgment.ability_score)}, 보정치 ${judgment.modifier >= 0 ? '+' : ''}${judgment.modifier}`}
                    >
                      <div className="text-xs text-slate-600 font-semibold mb-0.5">
                        능력치
                      </div>
                      <div className="flex items-baseline gap-1">
                        <span className="text-lg font-bold">
                          {getAbilityName(judgment.ability_score)}
                        </span>
                        <span className="text-sm text-slate-700">
                          {judgment.modifier >= 0 ? '+' : ''}{judgment.modifier}
                        </span>
                      </div>
                    </div>

                    {/* Difficulty */}
                    <div 
                      className="bg-white/50 rounded p-2"
                      role="group"
                      aria-label={`난이도: ${judgment.difficulty}`}
                    >
                      <div className="text-xs text-slate-600 font-semibold mb-0.5">
                        난이도
                      </div>
                      <div className="text-lg font-bold">
                        DC {judgment.difficulty}
                      </div>
                    </div>
                  </div>

                  {/* Dice Result */}
                  <div 
                    className="bg-white/50 rounded p-2"
                    role="group"
                    aria-label={`주사위 결과: ${judgment.dice_result}, 최종 값: ${judgment.final_value}`}
                  >
                    <div className="text-xs text-slate-600 font-semibold mb-1">
                      주사위 결과
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-2xl" role="img" aria-label="주사위">🎲</span>
                      <div className="flex items-baseline gap-2">
                        <span className="text-xl font-bold">
                          {judgment.dice_result}
                        </span>
                        {judgment.modifier !== 0 && (
                          <>
                            <span className="text-slate-500" aria-hidden="true">+</span>
                            <span className="text-lg text-slate-700">
                              {judgment.modifier}
                            </span>
                            <span className="text-slate-500" aria-hidden="true">=</span>
                            <span className="text-xl font-bold text-blue-600">
                              {judgment.final_value}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Outcome Reasoning */}
                  {judgment.outcome_reasoning && (
                    <div className="bg-white/50 rounded p-2">
                      <div className="text-xs text-slate-600 font-semibold mb-1">
                        결과 설명
                      </div>
                      <p className="text-sm text-slate-700 italic">
                        {judgment.outcome_reasoning}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Export memoized component to prevent unnecessary re-renders
export default memo(CompletedJudgmentsList);
