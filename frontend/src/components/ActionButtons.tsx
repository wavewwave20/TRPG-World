import { memo, useCallback } from "react";
import type { JudgmentStatus } from "../types/judgment";

interface ActionButtonsProps {
  status: JudgmentStatus;
  isLastJudgment: boolean;
  actionId: number;
  isCurrentPlayer: boolean;
  requiresRoll: boolean;
  onRollDice: (actionId: number) => void;
  onConfirmAction: (actionId: number) => void;
  onNext: () => void;
  onTriggerStory: () => void;
}

function ActionButtons({
  status,
  isLastJudgment,
  actionId,
  isCurrentPlayer,
  requiresRoll,
  onRollDice,
  onConfirmAction,
  onNext,
  onTriggerStory,
}: ActionButtonsProps) {
  const baseButtonClasses = "w-full py-3 sm:py-4 rounded-lg font-bold text-base sm:text-lg transition-all";
  const activeButtonClasses = "active:scale-95 shadow-lg hover:shadow-xl";

  const handleRollDiceClick = useCallback(() => {
    onRollDice(actionId);
  }, [onRollDice, actionId]);

  const handleConfirmClick = useCallback(() => {
    onConfirmAction(actionId);
  }, [onConfirmAction, actionId]);

  return (
    <div className="mt-4 space-y-2" role="group" aria-label="판정 액션">
      {status === "active" && isCurrentPlayer && requiresRoll && (
        <button
          onClick={handleRollDiceClick}
          className={`${baseButtonClasses} bg-blue-600 text-white hover:bg-blue-700 ${activeButtonClasses}`}
        >
          🎲 주사위 굴리기
        </button>
      )}

      {status === "active" && isCurrentPlayer && !requiresRoll && (
        <button
          onClick={handleConfirmClick}
          className={`${baseButtonClasses} bg-green-600 text-white hover:bg-green-700 ${activeButtonClasses}`}
        >
          확인
        </button>
      )}

      {status === "complete" && !isLastJudgment && isCurrentPlayer && (
        <button
          onClick={onNext}
          className={`${baseButtonClasses} bg-green-600 text-white hover:bg-green-700 ${activeButtonClasses}`}
        >
          확인
        </button>
      )}

      {status === "complete" && isLastJudgment && isCurrentPlayer && (
        <button
          onClick={onTriggerStory}
          className={`${baseButtonClasses} bg-purple-600 text-white hover:bg-purple-700 ${activeButtonClasses}`}
        >
          📖 이야기 진행
        </button>
      )}
    </div>
  );
}

export default memo(ActionButtons);
