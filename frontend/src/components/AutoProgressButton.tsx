import { memo, useEffect, useRef, useCallback } from 'react';

interface AutoProgressButtonProps {
  onClick: () => void;
  className: string;
  children: React.ReactNode;
  /** Auto-click delay in ms (default: 1000) */
  delay?: number;
}

/**
 * Button with a left-to-right gauge fill animation that auto-clicks after the delay.
 * Used for auto-progress (자동진행) judgments that don't require a dice roll.
 */
function AutoProgressButton({ onClick, className, children, delay = 2000 }: AutoProgressButtonProps) {
  const onClickRef = useRef(onClick);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const firedRef = useRef(false);

  onClickRef.current = onClick;

  const handleClick = useCallback(() => {
    if (firedRef.current) return;
    firedRef.current = true;
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    onClickRef.current();
  }, []);

  useEffect(() => {
    firedRef.current = false;
    timerRef.current = setTimeout(() => {
      if (!firedRef.current) {
        firedRef.current = true;
        onClickRef.current();
      }
    }, delay);

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [delay]);

  return (
    <button
      onClick={handleClick}
      className={`${className} auto-progress-button`}
    >
      <span
        className="auto-progress-fill"
        style={{ animationDuration: `${delay}ms` }}
      />
      <span className="relative z-10">{children}</span>
    </button>
  );
}

export default memo(AutoProgressButton);
