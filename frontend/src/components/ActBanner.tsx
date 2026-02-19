import { useMemo } from 'react';
import { useActStore } from '../stores/actStore';

export default function ActBanner() {
  const currentAct = useActStore((state) => state.currentAct);
  const growthHistory = useActStore((state) => state.growthHistory);

  const recentActs = useMemo(() => {
    if (!currentAct) return [];

    return [...growthHistory]
      .sort((a, b) => a.actNumber - b.actNumber)
      .filter((a) => a.actNumber < currentAct.actNumber)
      .slice(-3);
  }, [growthHistory, currentAct]);

  if (!currentAct) return null;

  const titleLine = `${currentAct.actNumber}막 · ${currentAct.title}`;

  return (
    <div className="px-4 py-3 sm:px-6 sm:py-4 bg-gradient-to-r from-amber-50 to-yellow-50 border-b border-amber-200/70">
      <div className="max-w-4xl mx-auto">
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

        {recentActs.length > 0 && (
          <div className="mt-3 pt-3 border-t border-amber-200/80">
            <div className="text-[11px] font-bold text-slate-600 text-center mb-2">이전 막</div>
            <div className="flex flex-wrap justify-center gap-2">
              {recentActs.map((act) => (
                <div
                  key={act.actId}
                  className="inline-flex items-center rounded-full border border-slate-300 bg-white px-2.5 py-1 text-[11px] text-slate-700"
                  title={act.actSubtitle || act.actTitle}
                >
                  {act.actNumber}막 {act.actTitle}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
