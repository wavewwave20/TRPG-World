import { useEffect, useState } from 'react';

interface DiceRollAnimationProps {
  result: number;
  modifier: number;
  finalValue: number;
  isCriticalSuccess?: boolean;
  isCriticalFailure?: boolean;
}

type Phase = 'shuffling' | 'diceResult' | 'showModifier' | 'finalValue';

const TIMINGS = {
  SHUFFLE_END: 700,
  MODIFIER_SHOW: 1200,
  FINAL_VALUE: 1900,
};

export default function DiceRollAnimation({
  result,
  modifier,
  finalValue,
  isCriticalSuccess = false,
  isCriticalFailure = false,
}: DiceRollAnimationProps) {
  const [phase, setPhase] = useState<Phase>('shuffling');
  const [displayNumber, setDisplayNumber] = useState(Math.floor(Math.random() * 20) + 1);
  const [announcement, setAnnouncement] = useState('주사위를 굴리는 중');

  // Shuffle: rapidly cycle random numbers
  useEffect(() => {
    if (phase !== 'shuffling') return;
    const interval = setInterval(() => {
      setDisplayNumber(Math.floor(Math.random() * 20) + 1);
    }, 50);
    return () => clearInterval(interval);
  }, [phase]);

  // Phase transitions
  useEffect(() => {
    const timers = [
      setTimeout(() => {
        setPhase('diceResult');
        setDisplayNumber(result);
        const resultText = isCriticalSuccess
          ? `대성공! 주사위 ${result}`
          : isCriticalFailure
          ? `대실패! 주사위 ${result}`
          : `주사위 ${result}`;
        setAnnouncement(resultText);
      }, TIMINGS.SHUFFLE_END),

      setTimeout(() => {
        setPhase('showModifier');
        setAnnouncement(`주사위 ${result}, 보정치 ${modifier >= 0 ? '+' : ''}${modifier}`);
      }, TIMINGS.MODIFIER_SHOW),

      setTimeout(() => {
        setPhase('finalValue');
        setAnnouncement(`최종 결과: ${finalValue}`);
      }, TIMINGS.FINAL_VALUE),
    ];
    return () => timers.forEach(clearTimeout);
  }, [result, modifier, finalValue, isCriticalSuccess, isCriticalFailure]);

  const resultColor = isCriticalSuccess
    ? 'text-amber-500'
    : isCriticalFailure
    ? 'text-red-500'
    : 'text-slate-800';

  const finalColor = isCriticalSuccess
    ? 'text-amber-500'
    : isCriticalFailure
    ? 'text-red-500'
    : 'text-blue-600';

  return (
    <div
      className="flex flex-col items-center justify-center p-4 h-[80px]"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <span className="sr-only">{announcement}</span>

      {phase === 'shuffling' && (
        <div className="dice-number-shuffle flex items-center justify-center" aria-hidden="true">
          <span className="text-4xl sm:text-5xl font-bold text-blue-400 tabular-nums inline-block min-w-[2.5ch] text-center">
            {displayNumber}
          </span>
        </div>
      )}

      {phase === 'diceResult' && (
        <div
          className={`dice-number-land flex items-center justify-center ${isCriticalSuccess ? 'critical-success' : ''} ${isCriticalFailure ? 'critical-failure' : ''}`}
          aria-hidden="true"
        >
          <span className={`text-4xl sm:text-5xl font-bold tabular-nums inline-block min-w-[2.5ch] text-center ${resultColor}`}>
            {result}
          </span>
        </div>
      )}

      {phase === 'showModifier' && (
        <div className="flex items-baseline justify-center gap-1" aria-hidden="true">
          <span className={`text-4xl sm:text-5xl font-bold tabular-nums inline-block min-w-[2.5ch] text-center ${resultColor}`}>
            {result}
          </span>
          <span className="dice-modifier-slide text-2xl sm:text-3xl font-bold text-slate-400 tabular-nums">
            {modifier >= 0 ? `+${modifier}` : `${modifier}`}
          </span>
        </div>
      )}

      {phase === 'finalValue' && (
        <div className="dice-final-value flex items-center justify-center" aria-hidden="true">
          <span className={`text-5xl sm:text-6xl font-bold tabular-nums inline-block min-w-[2.5ch] text-center ${finalColor}`}>
            {finalValue}
          </span>
        </div>
      )}
    </div>
  );
}
