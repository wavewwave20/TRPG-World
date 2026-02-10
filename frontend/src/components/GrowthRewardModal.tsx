import { useActStore } from '../stores/actStore';
import type { GrowthReward } from '../types/act';
import { ABILITY_LABELS, type AbilityKey } from '../types/character';

function GrowthIcon({ type }: { type: GrowthReward['growthType'] }) {
  switch (type) {
    case 'ability_increase':
      return <span className="text-lg">&#x2B06;</span>; // up arrow
    case 'new_skill':
      return <span className="text-lg">&#x2728;</span>; // sparkles
    case 'weakness_mitigated':
      return <span className="text-lg">&#x1F6E1;</span>; // shield
    default:
      return null;
  }
}

function growthTypeLabel(type: GrowthReward['growthType']): string {
  switch (type) {
    case 'ability_increase':
      return '능력치 상승';
    case 'new_skill':
      return '새 스킬 습득';
    case 'weakness_mitigated':
      return '약점 완화';
    default:
      return '성장';
  }
}

function GrowthDetail({ reward }: { reward: GrowthReward }) {
  const detail = reward.growthDetail;

  switch (reward.growthType) {
    case 'ability_increase': {
      const abilityKey = detail.ability as AbilityKey | undefined;
      const abilityName = abilityKey && ABILITY_LABELS[abilityKey]
        ? ABILITY_LABELS[abilityKey]
        : detail.ability ?? '???';
      const delta = detail.delta ?? 1;
      return (
        <span className="text-emerald-700 font-bold">
          {abilityName} +{delta}
        </span>
      );
    }
    case 'new_skill': {
      const skillName = detail.skill_name ?? detail.name ?? '???';
      return (
        <span className="text-blue-700 font-bold">
          {skillName}
        </span>
      );
    }
    case 'weakness_mitigated': {
      const weaknessName = detail.weakness ?? detail.name ?? '???';
      return (
        <span className="text-orange-700 font-bold">
          {weaknessName} 완화
        </span>
      );
    }
    default:
      return <span>{JSON.stringify(detail)}</span>;
  }
}

export default function GrowthRewardModal() {
  const showGrowthModal = useActStore((state) => state.showGrowthModal);
  const growthRewards = useActStore((state) => state.growthRewards);
  const setShowGrowthModal = useActStore((state) => state.setShowGrowthModal);

  if (!showGrowthModal || growthRewards.length === 0) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => setShowGrowthModal(false)}
      />

      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-2xl max-w-lg w-full mx-4 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 bg-gradient-to-r from-amber-50 to-yellow-50 border-b border-amber-200/60 text-center">
          <div className="text-xs font-bold text-amber-700 uppercase tracking-widest mb-1">
            막 전환 완료
          </div>
          <h2 className="text-lg font-bold text-slate-800">
            성장 보상
          </h2>
        </div>

        {/* Reward Cards */}
        <div className="px-6 py-4 space-y-3 max-h-[60vh] overflow-y-auto">
          {growthRewards.map((reward, index) => (
            <div
              key={index}
              className="border border-slate-200 rounded-xl p-4 bg-slate-50/50"
            >
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
                  <GrowthIcon type={reward.growthType} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-bold text-sm text-slate-800">
                      {reward.characterName}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">
                      {growthTypeLabel(reward.growthType)}
                    </span>
                  </div>
                  <div className="text-sm mb-1.5">
                    <GrowthDetail reward={reward} />
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed">
                    {reward.narrativeReason}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-200 flex justify-center">
          <button
            onClick={() => setShowGrowthModal(false)}
            className="bg-amber-600 hover:bg-amber-700 text-white px-8 py-2.5 rounded-lg text-sm font-bold shadow-sm transition-all"
          >
            확인
          </button>
        </div>
      </div>
    </div>
  );
}
