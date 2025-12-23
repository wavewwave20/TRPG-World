import { memo, useMemo } from 'react';

interface JudgmentModalHeaderProps {
  /** Current judgment index (0-based) */
  currentIndex: number;
  /** Total number of judgments */
  totalCount: number;
  /** Callback to close the modal */
  onClose?: () => void;
}

/**
 * JudgmentModalHeader - Header component for the judgment modal
 * 
 * Displays the current judgment progress with a visual indicator showing
 * which judgment is currently active out of the total. Includes a progress
 * bar that fills as judgments are completed.
 * 
 * Features:
 * - Current judgment number and total count (e.g., "2 / 5")
 * - Visual progress bar showing completion percentage
 * - Responsive design for mobile and desktop
 * - Accessible with proper ARIA labels
 * - Performance optimized with React.memo and useMemo
 * 
 * Requirements:
 * - 2.1: Display current judgment prominently in modal
 * - 4.1: Show progress indicator at top of modal (X / Y format)
 * - 5.2: Responsive styling for mobile and desktop
 * - 10.1: Prevent unnecessary re-renders with React.memo
 * - 10.4: Memoize computed values
 * 
 * @param props - Component props
 * @returns Header component with progress display
 */
function JudgmentModalHeader({
  currentIndex,
  totalCount,
  onClose,
}: JudgmentModalHeaderProps) {
  // Memoize progress percentage calculation to avoid recalculation on every render
  const progressPercentage = useMemo(() => {
    return totalCount > 0 
      ? ((currentIndex + 1) / totalCount) * 100 
      : 0;
  }, [currentIndex, totalCount]);

  return (
    <div className="sticky top-0 bg-white border-b border-slate-200 px-4 sm:px-6 py-4 rounded-t-xl z-10">
      {/* Title and counter */}
      <div className="flex items-center justify-between mb-3">
        <h2
          id="judgment-modal-title"
          className="text-lg sm:text-xl font-bold text-slate-800"
        >
          판정 진행 중
        </h2>
        <div className="flex items-center gap-2">
          <div
            className="text-sm sm:text-base font-semibold text-slate-600 bg-slate-100 px-3 py-1 rounded-full"
            aria-label={`${currentIndex + 1}번째 판정, 총 ${totalCount}개 중`}
          >
            {currentIndex + 1} / {totalCount}
          </div>
          {/* Close button */}
          {onClose && (
            <button
              onClick={onClose}
              className="w-8 h-8 flex items-center justify-center rounded-full bg-slate-100 hover:bg-slate-200 text-slate-600 hover:text-slate-800 transition-colors"
              aria-label="모달 닫기"
              title="모달 닫기 (ESC)"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div
        className="w-full bg-slate-200 rounded-full h-2 overflow-hidden"
        role="progressbar"
        aria-valuenow={currentIndex + 1}
        aria-valuemin={1}
        aria-valuemax={totalCount}
        aria-label="판정 진행 상황"
      >
        <div
          className="bg-gradient-to-r from-blue-500 to-indigo-600 h-full rounded-full transition-all duration-500 ease-out"
          style={{ width: `${progressPercentage}%` }}
        />
      </div>

      {/* Progress text for screen readers */}
      <p
        id="judgment-modal-description"
        className="sr-only"
      >
        현재 {currentIndex + 1}번째 판정을 진행 중입니다. 총 {totalCount}개의 판정 중 {progressPercentage.toFixed(0)}% 완료되었습니다.
      </p>
    </div>
  );
}

// Export memoized component to prevent unnecessary re-renders
export default memo(JudgmentModalHeader);
