import { memo, useMemo } from 'react';
import type { JudgmentResult } from '../types/judgment';

interface ResultDisplayProps {
  /** The judgment result to display */
  judgment: JudgmentResult;
}

/**
 * ResultDisplay - Displays the results of a completed judgment
 * 
 * This component shows:
 * - Dice roll result (1-20)
 * - Final value (dice + modifier)
 * - Success/failure outcome with appropriate colors and icons
 * - Outcome reasoning text
 * 
 * Performance optimized with React.memo and useMemo.
 * 
 * Requirements:
 * - 3.5: Display dice results with emphasis and color-coded success/failure
 * - 7.4: Show results with appropriate colors and icons
 * - 10.1: Prevent unnecessary re-renders with React.memo
 * - 10.4: Memoize computed values
 * 
 * @param props - Component props
 * @returns Result display component
 */
function ResultDisplay({ judgment }: ResultDisplayProps) {
  // Memoize outcome color to avoid recalculation
  const outcomeColor = useMemo(() => {
    switch (judgment.outcome) {
      case 'critical_success':
        return 'text-amber-600 bg-amber-50 border-amber-300';
      case 'success':
        return 'text-green-600 bg-green-50 border-green-300';
      case 'failure':
        return 'text-orange-600 bg-orange-50 border-orange-300';
      case 'critical_failure':
        return 'text-red-600 bg-red-50 border-red-300';
      default:
        return 'text-slate-600 bg-slate-50 border-slate-300';
    }
  }, [judgment.outcome]);

  // Memoize outcome text to avoid recalculation
  const outcomeText = useMemo(() => {
    switch (judgment.outcome) {
      case 'critical_success':
        return '⭐ 대성공!';
      case 'success':
        return '✅ 성공';
      case 'failure':
        return '❌ 실패';
      case 'critical_failure':
        return '💥  대실패!';
      default:
        return judgment.outcome;
    }
  }, [judgment.outcome]);

  // Memoize dice icon to avoid recalculation
  const diceIcon = useMemo(() => {
    switch (judgment.outcome) {
      case 'critical_success':
        return '🎲✨';
      case 'critical_failure':
        return '🎲💔';
      default:
        return '🎲';
    }
  }, [judgment.outcome]);

  // Memoize screen reader announcement
  const outcomeAnnouncement = useMemo(() => {
    return `판정 결과: 주사위 ${judgment.dice_result}, 보정치 ${judgment.modifier >= 0 ? '+' : ''}${judgment.modifier}, 최종 값 ${judgment.final_value}, ${outcomeText}`;
  }, [judgment.dice_result, judgment.modifier, judgment.final_value, outcomeText]);

  return (
    <div className="space-y-3" role="region" aria-label="판정 결과">
      {/* Screen Reader Announcement */}
      <div className="sr-only" role="status" aria-live="assertive" aria-atomic="true">
        {outcomeAnnouncement}
      </div>

      {/* Dice Result Card */}
      <div 
        className="p-4 bg-white rounded-lg border-2 border-slate-200 shadow-sm"
        role="group"
        aria-label="주사위 굴림 결과"
      >
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-semibold text-slate-600">
            {diceIcon} 주사위 결과
          </span>
          <span 
            className="text-3xl sm:text-4xl font-bold text-slate-800"
            aria-label={`주사위 결과: ${judgment.dice_result}`}
          >
            {judgment.dice_result}
          </span>
        </div>
        
        <div className="flex items-center justify-between pt-3 border-t border-slate-100">
          <span className="text-sm font-semibold text-slate-600">최종 값</span>
          <div className="flex items-baseline gap-2">
            <span 
              className="text-2xl sm:text-3xl font-bold text-blue-600"
              aria-label={`최종 값: ${judgment.final_value}, 계산: ${judgment.dice_result} 더하기 ${judgment.modifier}`}
            >
              {judgment.final_value}
            </span>
            <span className="text-xs sm:text-sm text-slate-500" aria-hidden="true">
              ({judgment.dice_result} + {judgment.modifier})
            </span>
          </div>
        </div>
      </div>

      {/* Outcome Card */}
      <div 
        className={`p-4 rounded-lg border-2 shadow-sm ${outcomeColor}`}
        role="alert"
        aria-label={`판정 결과: ${outcomeText}`}
      >
        <div className="text-center mb-2">
          <span className="text-2xl sm:text-3xl font-bold">
            {outcomeText}
          </span>
        </div>
        
        {judgment.outcome_reasoning && (
          <div className="mt-3 pt-3 border-t border-current border-opacity-20">
            <p className="text-sm sm:text-base text-center leading-relaxed">
              {judgment.outcome_reasoning}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// Export memoized component to prevent unnecessary re-renders
export default memo(ResultDisplay);
