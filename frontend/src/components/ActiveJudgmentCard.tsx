import { memo, useMemo } from 'react';
import type { JudgmentSetup, JudgmentResult } from '../types/judgment';
import DiceRollAnimation from './DiceRollAnimation';
import ResultDisplay from './ResultDisplay';
import ActionButtons from './ActionButtons';

interface ActiveJudgmentCardProps {
  /** The current judgment being displayed */
  judgment: JudgmentSetup | JudgmentResult;
  /** Whether the local user owns this judgment */
  isCurrentPlayer: boolean;
  /** Callback when dice roll button is clicked */
  onRollDice: (actionId: number) => void;
  /** Callback when next button is clicked */
  onNext: () => void;
  /** Callback when trigger story button is clicked */
  onTriggerStory: () => void;
  /** Whether this is the last judgment in the sequence */
  isLastJudgment: boolean;
}

/**
 * ActiveJudgmentCard - Displays the current active judgment
 * 
 * This component shows all information about the current judgment including:
 * - Character information (name, avatar)
 * - Action text
 * - Ability score and difficulty
 * - Dice rolling animation (when rolling)
 * - Results (when complete)
 * - Action buttons (roll dice, next, trigger story)
 * 
 * Performance optimized with React.memo and useMemo.
 * 
 * Requirements:
 * - 2.1: Display current judgment prominently in modal
 * - 2.2: Show character name and avatar prominently
 * - 2.3: Format action text with readable size and spacing
 * - 2.4: Display ability score and difficulty in visually distinct cards
 * - 5.2: Apply responsive layout for mobile and desktop
 * - 10.1: Prevent unnecessary re-renders with React.memo
 * - 10.4: Memoize computed values
 * 
 * @param props - Component props
 * @returns Active judgment card component
 */
function ActiveJudgmentCard({
  judgment,
  isCurrentPlayer,
  onRollDice,
  onNext,
  onTriggerStory,
  isLastJudgment
}: ActiveJudgmentCardProps) {
  const isJudgmentResult = (j: JudgmentSetup | JudgmentResult): j is JudgmentResult => {
    return 'dice_result' in j;
  };

  // Memoize ability name lookup to avoid recalculation
  const abilityName = useMemo(() => {
    const abilityNames: Record<string, string> = {
      str: '근력',
      dex: '민첩',
      con: '건강',
      int: '지능',
      wis: '지혜',
      cha: '매력'
    };
    return abilityNames[judgment.ability_score] || judgment.ability_score.toUpperCase();
  }, [judgment.ability_score]);

  // Memoize character avatar initial
  const avatarInitial = useMemo(() => {
    return judgment.character_name.charAt(0).toUpperCase();
  }, [judgment.character_name]);

  return (
    <div 
      className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-4 sm:p-6 border-2 border-blue-300"
      role="article"
      aria-label={`${judgment.character_name}의 현재 판정`}
    >
      {/* Character Info */}
      <div className="flex items-center gap-3 mb-4">
        <div 
          className="w-12 h-12 sm:w-14 sm:h-14 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-xl sm:text-2xl shadow-lg"
          role="img"
          aria-label={`${judgment.character_name}의 아바타`}
        >
          {avatarInitial}
        </div>
        <div className="flex-1">
          <h3 
            id="judgment-modal-title"
            className="text-lg sm:text-xl font-bold text-slate-800"
          >
            {judgment.character_name}
          </h3>
          <p 
            id="judgment-modal-description"
            className="text-xs sm:text-sm text-slate-600"
          >
            판정 진행 중
          </p>
        </div>
      </div>

      {/* Action Text */}
      <div 
        className="mb-4 p-3 sm:p-4 bg-white rounded-lg border border-blue-200"
        role="region"
        aria-label="행동 내용"
      >
        <p className="text-sm sm:text-base text-slate-700 leading-relaxed">
          {judgment.action_text}
        </p>
      </div>

      {/* Stats Display - Ability Score and Difficulty */}
      <div 
        className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4"
        role="region"
        aria-label="판정 정보"
      >
        {/* Ability Score Card */}
        <div 
          className="bg-white rounded-lg p-3 sm:p-4 border-2 border-blue-200"
          role="group"
          aria-label={`능력치: ${abilityName}, 보정치 ${judgment.modifier >= 0 ? '+' : ''}${judgment.modifier}`}
        >
          <div className="text-xs sm:text-sm text-slate-600 font-semibold mb-1">
            능력치
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-bold text-blue-600">
              {abilityName}
            </span>
            <span className="text-lg sm:text-xl text-slate-700">
              {judgment.modifier >= 0 ? '+' : ''}{judgment.modifier}
            </span>
          </div>
        </div>

        {/* Difficulty Card */}
        <div 
          className="bg-white rounded-lg p-3 sm:p-4 border-2 border-indigo-200"
          role="group"
          aria-label={`난이도: ${judgment.difficulty}`}
        >
          <div className="text-xs sm:text-sm text-slate-600 font-semibold mb-1">
            난이도 (DC)
          </div>
          <div className="text-2xl sm:text-3xl font-bold text-indigo-600">
            {judgment.difficulty}
          </div>
        </div>
      </div>

      {/* Difficulty Reasoning */}
      {judgment.difficulty_reasoning && (
        <div 
          className="mb-4 p-3 bg-white/60 rounded-lg border border-blue-100"
          role="note"
          aria-label="난이도 설명"
        >
          <p className="text-xs sm:text-sm text-slate-600 italic">
            💡 {judgment.difficulty_reasoning}
          </p>
        </div>
      )}

      {/* Dice Rolling Animation */}
      {judgment.status === 'rolling' && isJudgmentResult(judgment) && (
        <div 
          className="my-4 p-4 bg-white rounded-lg border-2 border-blue-300"
          role="status"
          aria-live="polite"
          aria-label="주사위를 굴리는 중입니다"
        >
          <DiceRollAnimation
            result={judgment.dice_result}
            isCriticalSuccess={judgment.dice_result === 20}
            isCriticalFailure={judgment.dice_result === 1}
          />
        </div>
      )}

      {/* Result Display */}
      {judgment.status === 'complete' && isJudgmentResult(judgment) && (
        <div className="my-4">
          <ResultDisplay judgment={judgment} />
        </div>
      )}

      {/* Waiting notice for non-owners */}
      {!isCurrentPlayer && (
        <div className="mt-2 text-xs text-slate-500 italic">
          {judgment.status === 'active' && (
            <span>⏳ {judgment.character_name}의 주사위 굴림을 기다리는 중...</span>
          )}
          {judgment.status === 'complete' && (
            <span>⏳ {judgment.character_name}의 확인을 기다리는 중...</span>
          )}
        </div>
      )}

      {/* Action Buttons */}
      <ActionButtons
        status={judgment.status}
        isLastJudgment={isLastJudgment}
        actionId={judgment.action_id}
        isCurrentPlayer={isCurrentPlayer}
        onRollDice={onRollDice}
        onNext={onNext}
        onTriggerStory={onTriggerStory}
      />
    </div>
  );
}

// Export memoized component to prevent unnecessary re-renders
export default memo(ActiveJudgmentCard);
