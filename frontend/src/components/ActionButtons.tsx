import { memo, useCallback } from "react";
import type { JudgmentStatus } from "../types/judgment";
import AutoProgressButton from "./AutoProgressButton";
import DiceRollButton from "./DiceRollButton";

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
      {/* Roll dice - press & hold to charge, release to throw */}
      {status === "active" && isCurrentPlayer && requiresRoll && (
        <DiceRollButton
          onClick={handleRollDiceClick}
          className={`${baseButtonClasses} bg-blue-600 text-white hover:bg-blue-700 shadow-lg hover:shadow-xl`}
        >
          🎲 주사위 굴리기
        </DiceRollButton>
      )}

      {/* Auto-progress confirm - gauge fill + auto-click */}
      {status === "active" && isCurrentPlayer && !requiresRoll && (
        <AutoProgressButton
          onClick={handleConfirmClick}
          className={`${baseButtonClasses} bg-green-600 text-white hover:bg-green-700 ${activeButtonClasses}`}
        >
          확인
        </AutoProgressButton>
      )}

      {/* Next judgment - regular button when roll was required */}
      {status === "complete" && !isLastJudgment && isCurrentPlayer && requiresRoll && (
        <button
          onClick={onNext}
          className={`${baseButtonClasses} bg-green-600 text-white hover:bg-green-700 ${activeButtonClasses}`}
        >
          확인
        </button>
      )}

      {/* Next judgment - auto-progress when no roll was needed */}
      {status === "complete" && !isLastJudgment && isCurrentPlayer && !requiresRoll && (
        <AutoProgressButton
          onClick={onNext}
          className={`${baseButtonClasses} bg-green-600 text-white hover:bg-green-700 ${activeButtonClasses}`}
        >
          확인
        </AutoProgressButton>
      )}

      {/* Story trigger - regular button when roll was required */}
      {status === "complete" && isLastJudgment && isCurrentPlayer && requiresRoll && (
        <button
          onClick={onTriggerStory}
          className={`${baseButtonClasses} bg-purple-600 text-white hover:bg-purple-700 ${activeButtonClasses}`}
        >
          📖 이야기 진행
        </button>
      )}

      {/* Story trigger - auto-progress when no roll was needed */}
      {status === "complete" && isLastJudgment && isCurrentPlayer && !requiresRoll && (
        <AutoProgressButton
          onClick={onTriggerStory}
          className={`${baseButtonClasses} bg-purple-600 text-white hover:bg-purple-700 ${activeButtonClasses}`}
        >
          📖 이야기 진행
        </AutoProgressButton>
      )}
    </div>
  );
}

export default memo(ActionButtons);
