import { memo } from 'react';
import type { JudgmentSetup } from '../types/judgment';

interface WaitingIndicatorProps {
  /** Array of judgments that are still waiting to be processed */
  waitingJudgments: JudgmentSetup[];
}

/**
 * WaitingIndicator - Displays the number of judgments waiting to be processed
 * 
 * This component shows a simple visual indicator of how many judgments
 * are still pending after the current one. It provides players with
 * awareness of the remaining judgments in the queue.
 * 
 * Features:
 * - Shows count of waiting judgments
 * - Simple icon and text display
 * - Responsive design
 * - Only renders when there are waiting judgments
 * - Performance optimized with React.memo
 * 
 * Requirements:
 * - 4.2: Display the number of waiting judgments
 * - 10.1: Prevent unnecessary re-renders with React.memo
 * 
 * @param props - Component props
 * @returns Waiting indicator component or null if no waiting judgments
 */
function WaitingIndicator({ waitingJudgments }: WaitingIndicatorProps) {
  if (waitingJudgments.length === 0) {
    return null;
  }

  return (
    <div 
      className="bg-slate-50 border-2 border-slate-200 rounded-lg p-3 sm:p-4"
      role="status"
      aria-label={`대기 중인 판정: ${waitingJudgments.length}개`}
    >
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Icon */}
        <div className="flex-shrink-0 w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-slate-200 flex items-center justify-center">
          <span className="text-xl sm:text-2xl" role="img" aria-label="대기 중">
            ⏳
          </span>
        </div>

        {/* Text Content */}
        <div className="flex-1 min-w-0">
          <div className="text-sm sm:text-base font-semibold text-slate-700">
            대기 중인 판정
          </div>
          <div className="text-xs sm:text-sm text-slate-600">
            {waitingJudgments.length}개의 판정이 대기 중입니다
          </div>
        </div>

        {/* Count Badge */}
        <div 
          className="flex-shrink-0 w-8 h-8 sm:w-10 sm:h-10 rounded-full bg-slate-300 flex items-center justify-center"
          aria-label={`대기 중인 판정 수: ${waitingJudgments.length}`}
        >
          <span className="text-sm sm:text-base font-bold text-slate-700">
            {waitingJudgments.length}
          </span>
        </div>
      </div>

      {/* Optional: Show character names in waiting */}
      {waitingJudgments.length > 0 && waitingJudgments.length <= 3 && (
        <div 
          className="mt-2 pt-2 border-t border-slate-200"
          role="list"
          aria-label="대기 중인 캐릭터 목록"
        >
          <div className="text-xs text-slate-600 space-y-1">
            {waitingJudgments.map((judgment) => (
              <div 
                key={judgment.action_id} 
                className="flex items-center gap-2"
                role="listitem"
              >
                <div 
                  className="w-5 h-5 rounded-full bg-gradient-to-br from-slate-300 to-slate-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                  role="img"
                  aria-label={`${judgment.character_name}의 아바타`}
                >
                  {judgment.character_name.charAt(0).toUpperCase()}
                </div>
                <span className="truncate">{judgment.character_name}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Export memoized component to prevent unnecessary re-renders
export default memo(WaitingIndicator);
