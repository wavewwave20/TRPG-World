import { useState } from 'react';
import { useActStore } from '../stores/actStore';

export default function ActBanner() {
  const currentAct = useActStore((state) => state.currentAct);
  const [mobileExpanded, setMobileExpanded] = useState(false);

  if (!currentAct) return null;

  const titleLine = `${currentAct.actNumber}막 · ${currentAct.title}`;

  return (
    <div className="px-3 py-2 sm:px-6 sm:py-4 bg-gradient-to-r from-amber-50 to-yellow-50 border-b border-amber-200/70">
      <div className="max-w-4xl mx-auto">
        {/* Mobile: compact + collapsible */}
        <div className="sm:hidden">
          <button
            type="button"
            onClick={() => setMobileExpanded((v) => !v)}
            className="w-full flex items-center justify-between rounded-lg border border-amber-300 bg-white/80 px-3 py-2"
          >
            <span className="text-xs font-extrabold text-slate-800 truncate">{titleLine}</span>
            <span className={`text-[10px] text-slate-500 transition-transform ${mobileExpanded ? 'rotate-180' : ''}`}>
              ▼
            </span>
          </button>

          {mobileExpanded && (
            <div className="mt-2 rounded-lg border border-amber-200 bg-white/70 px-3 py-2">
              {currentAct.subtitle && (
                <div className="text-[11px] text-slate-600 font-medium">{currentAct.subtitle}</div>
              )}
              <div className="mt-1 text-[10px] text-slate-500">
                시작: {new Date(currentAct.startedAt).toLocaleString('ko-KR')}
              </div>
            </div>
          )}
        </div>

        {/* Desktop/tablet: expanded */}
        <div className="hidden sm:block">
          <div className="text-sm sm:text-base font-extrabold text-slate-800 tracking-tight text-center">
            {titleLine}
          </div>

          {currentAct.subtitle && (
            <div className="text-xs sm:text-sm text-slate-600 mt-1 text-center font-medium">
              {currentAct.subtitle}
            </div>
          )}

          <div className="mt-2 flex flex-wrap items-center justify-center gap-2 text-[11px]">
            <span className="inline-flex items-center rounded-full border border-amber-300 bg-white/80 px-2 py-0.5 text-amber-800 font-semibold">
              현재 진행 막
            </span>
            <span className="text-slate-500">
              시작: {new Date(currentAct.startedAt).toLocaleString('ko-KR')}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
