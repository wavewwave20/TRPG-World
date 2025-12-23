import { useEffect, useState } from 'react';

interface DiceRollAnimationProps {
  result: number;
  isCriticalSuccess?: boolean;  // Natural 20
  isCriticalFailure?: boolean;  // Natural 1
  onComplete?: () => void;
}

export default function DiceRollAnimation({
  result,
  isCriticalSuccess = false,
  isCriticalFailure = false,
  onComplete
}: DiceRollAnimationProps) {
  const [phase, setPhase] = useState<'rolling' | 'result'>('rolling');
  const [announcement, setAnnouncement] = useState<string>('');

  useEffect(() => {
    // Announce rolling to screen readers
    setAnnouncement('주사위를 굴리는 중');

    // Rolling animation duration: 0.8s
    const rollTimer = setTimeout(() => {
      setPhase('result');
      // Announce result to screen readers
      const resultText = isCriticalSuccess 
        ? `대성공! 주사위 결과 ${result}` 
        : isCriticalFailure 
        ? `대실패! 주사위 결과 ${result}` 
        : `주사위 결과 ${result}`;
      setAnnouncement(resultText);
    }, 800);

    // Complete animation after result is shown (0.8s roll + 0.4s result display)
    const completeTimer = setTimeout(() => {
      onComplete?.();
    }, 1200);

    return () => {
      clearTimeout(rollTimer);
      clearTimeout(completeTimer);
    };
  }, [onComplete, result, isCriticalSuccess, isCriticalFailure]);

  return (
    <div 
      className="flex flex-col items-center justify-center p-3 sm:p-4"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      {/* Screen reader announcement */}
      <span className="sr-only">{announcement}</span>

      {phase === 'rolling' ? (
        <div className="dice-rolling" aria-hidden="true">
          <svg
            className="w-12 h-12 sm:w-14 sm:h-14 md:w-16 md:h-16 text-blue-500"
            fill="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
            aria-label="주사위 굴리는 중"
          >
            {/* D20 dice icon */}
            <path d="M12 2L2 7v10l10 5 10-5V7L12 2zm0 2.18L19.82 8 12 11.82 4.18 8 12 4.18zM4 9.48l7 3.5v7.84l-7-3.5V9.48zm16 0v7.84l-7 3.5v-7.84l7-3.5z" />
          </svg>
        </div>
      ) : (
        <div
          className={`dice-result ${
            isCriticalFailure
              ? 'critical-failure'
              : isCriticalSuccess
              ? 'critical-success'
              : ''
          }`}
          aria-label={`주사위 결과: ${result}${isCriticalSuccess ? ', 대성공' : isCriticalFailure ? ', 대실패' : ''}`}
        >
          <div className="text-4xl sm:text-5xl md:text-6xl font-bold" aria-hidden="true">{result}</div>
        </div>
      )}

      <style>{`
        @keyframes dice-spin {
          0% {
            transform: rotate(0deg) scale(1);
          }
          25% {
            transform: rotate(90deg) scale(1.1);
          }
          50% {
            transform: rotate(180deg) scale(1);
          }
          75% {
            transform: rotate(270deg) scale(1.1);
          }
          100% {
            transform: rotate(360deg) scale(1);
          }
        }

        @keyframes dice-bounce {
          0%, 100% {
            transform: translateY(0) scale(1);
          }
          25% {
            transform: translateY(-10px) scale(1.05);
          }
          50% {
            transform: translateY(0) scale(1);
          }
          75% {
            transform: translateY(-5px) scale(1.02);
          }
        }

        @keyframes fade-scale-in {
          0% {
            opacity: 0;
            transform: scale(0.5);
          }
          100% {
            opacity: 1;
            transform: scale(1);
          }
        }

        @keyframes critical-shake {
          0%, 100% {
            transform: translateX(0) rotate(0deg);
          }
          10%, 30%, 50%, 70%, 90% {
            transform: translateX(-5px) rotate(-2deg);
          }
          20%, 40%, 60%, 80% {
            transform: translateX(5px) rotate(2deg);
          }
        }

        @keyframes critical-sparkle {
          0%, 100% {
            transform: scale(1) rotate(0deg);
            filter: brightness(1);
          }
          25% {
            transform: scale(1.1) rotate(5deg);
            filter: brightness(1.3);
          }
          50% {
            transform: scale(1.2) rotate(-5deg);
            filter: brightness(1.5);
          }
          75% {
            transform: scale(1.1) rotate(5deg);
            filter: brightness(1.3);
          }
        }

        /* Mobile-optimized animations - reduce complexity on small screens */
        @media (max-width: 767px) {
          @keyframes dice-spin {
            0% {
              transform: rotate(0deg);
            }
            100% {
              transform: rotate(360deg);
            }
          }

          @keyframes dice-bounce {
            0%, 100% {
              transform: translateY(0);
            }
            50% {
              transform: translateY(-8px);
            }
          }

          @keyframes critical-shake {
            0%, 100% {
              transform: translateX(0);
            }
            25%, 75% {
              transform: translateX(-3px);
            }
            50% {
              transform: translateX(3px);
            }
          }

          @keyframes critical-sparkle {
            0%, 100% {
              filter: brightness(1);
            }
            50% {
              filter: brightness(1.3);
            }
          }
        }

        /* Reduce motion for users who prefer it */
        @media (prefers-reduced-motion: reduce) {
          @keyframes dice-spin {
            0% {
              opacity: 0.5;
            }
            100% {
              opacity: 1;
            }
          }

          @keyframes dice-bounce {
            0% {
              opacity: 0;
            }
            100% {
              opacity: 1;
            }
          }

          @keyframes critical-shake,
          @keyframes critical-sparkle {
            0%, 100% {
              opacity: 1;
            }
          }

          .dice-rolling svg {
            animation: dice-spin 0.3s ease-out;
          }

          .dice-result {
            animation: fade-scale-in 0.2s ease-out;
          }

          .dice-result.critical-failure,
          .dice-result.critical-success {
            animation: fade-scale-in 0.2s ease-out;
          }
        }

        .dice-rolling svg {
          animation: dice-spin 0.8s cubic-bezier(0.68, -0.55, 0.265, 1.55);
          will-change: transform;
        }

        .dice-result {
          animation: dice-bounce 0.4s ease-out, fade-scale-in 0.3s ease-out;
          will-change: transform, opacity;
        }

        .dice-result.critical-failure {
          color: #dc2626;
          animation: dice-bounce 0.4s ease-out, fade-scale-in 0.3s ease-out, critical-shake 0.5s ease-in-out 0.3s;
          will-change: transform, opacity;
        }

        .dice-result.critical-success {
          color: #f59e0b;
          animation: dice-bounce 0.4s ease-out, fade-scale-in 0.3s ease-out, critical-sparkle 0.6s ease-in-out 0.3s;
          text-shadow: 0 0 10px rgba(245, 158, 11, 0.5);
          will-change: transform, opacity, filter;
        }
      `}</style>
    </div>
  );
}
