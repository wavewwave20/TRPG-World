import { useActStore } from '../stores/actStore';

export default function ActBanner() {
  const currentAct = useActStore((state) => state.currentAct);

  if (!currentAct) return null;

  return (
    <div className="px-6 py-3 bg-gradient-to-r from-amber-50 to-yellow-50 border-b border-amber-200/60 text-center">
      <div className="text-xs font-bold text-amber-700 uppercase tracking-widest mb-0.5">
        {currentAct.actNumber}막
      </div>
      <div className="text-sm font-bold text-slate-800">
        {currentAct.title}
      </div>
      {currentAct.subtitle && (
        <div className="text-xs text-slate-500 mt-0.5">
          {currentAct.subtitle}
        </div>
      )}
    </div>
  );
}
