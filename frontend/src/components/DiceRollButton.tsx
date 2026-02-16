import { memo, useRef, useCallback, useState, useEffect } from 'react';

/** Must match .dice-charge-fill transition duration in JudgmentModal.css */
const CHARGE_DURATION_MS = 600;

interface DiceRollButtonProps {
  onClick: () => void;
  className: string;
  children: React.ReactNode;
}

/**
 * Press-and-hold dice roll button.
 * Hold down to charge (gauge fills + color shift).
 * Release AFTER fully charged to throw. Release early = cancel.
 */
function DiceRollButton({ onClick, className, children }: DiceRollButtonProps) {
  const [isCharging, setIsCharging] = useState(false);
  const [isCharged, setIsCharged] = useState(false);
  const chargingRef = useRef(false);
  const chargedRef = useRef(false);
  const chargeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onClickRef = useRef(onClick);
  onClickRef.current = onClick;

  const clearChargeTimer = useCallback(() => {
    if (chargeTimerRef.current) {
      clearTimeout(chargeTimerRef.current);
      chargeTimerRef.current = null;
    }
  }, []);

  const handlePointerDown = useCallback(() => {
    chargingRef.current = true;
    chargedRef.current = false;
    setIsCharging(true);
    setIsCharged(false);

    chargeTimerRef.current = setTimeout(() => {
      chargedRef.current = true;
      setIsCharged(true);
    }, CHARGE_DURATION_MS);
  }, []);

  const handlePointerUp = useCallback(() => {
    if (chargingRef.current && chargedRef.current) {
      // Fully charged — fire!
      chargingRef.current = false;
      chargedRef.current = false;
      setIsCharging(false);
      setIsCharged(false);
      clearChargeTimer();
      onClickRef.current();
    } else {
      // Released too early — cancel
      chargingRef.current = false;
      chargedRef.current = false;
      setIsCharging(false);
      setIsCharged(false);
      clearChargeTimer();
    }
  }, [clearChargeTimer]);

  const handleCancel = useCallback(() => {
    chargingRef.current = false;
    chargedRef.current = false;
    setIsCharging(false);
    setIsCharged(false);
    clearChargeTimer();
  }, [clearChargeTimer]);

  // Cleanup on unmount
  useEffect(() => {
    return () => clearChargeTimer();
  }, [clearChargeTimer]);

  // Keyboard accessibility: Enter/Space triggers immediately
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClickRef.current();
    }
  }, []);

  return (
    <button
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onPointerLeave={handleCancel}
      onPointerCancel={handleCancel}
      onKeyDown={handleKeyDown}
      className={`${className} dice-roll-button ${isCharging ? 'charging' : ''} ${isCharged ? 'charged' : ''}`}
    >
      <span className="dice-charge-fill" />
      <span className="relative z-10">
        {isCharged ? '🎲 놓으면 던집니다!' : children}
      </span>
    </button>
  );
}

export default memo(DiceRollButton);
