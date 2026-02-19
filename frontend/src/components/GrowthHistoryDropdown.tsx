import { useState, useRef, useEffect } from 'react';
import { useActStore } from '../stores/actStore';

export default function GrowthHistoryDropdown() {
  const growthHistory = useActStore((s) => s.growthHistory);
  const showHistoryRewards = useActStore((s) => s.showHistoryRewards);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // 외부 클릭 시 닫기
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  if (growthHistory.length === 0) return null;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-300 px-3 py-2.5 lg:py-1.5 rounded-lg text-xs font-semibold shadow-sm transition-all"
      >
        성장 기록
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-56 bg-white border border-slate-200 rounded-lg shadow-lg z-50 overflow-hidden">
          {growthHistory.map((entry) => (
            <button
              key={entry.actId}
              onClick={() => {
                showHistoryRewards(entry.actId);
                setOpen(false);
              }}
              className="w-full text-left px-4 py-2.5 hover:bg-slate-50 border-b border-slate-100 last:border-b-0 transition-colors"
            >
              <div className="text-xs font-bold text-slate-700">
                {entry.actNumber}막 — {entry.actTitle}
              </div>
              <div className="text-[11px] text-slate-400">
                보상 {entry.rewards.length}개
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
