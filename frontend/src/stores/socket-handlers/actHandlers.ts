import type { Socket } from 'socket.io-client';
import type { StoryActInfo, GrowthReward } from '../../types/act';
import { useGameStore } from '../gameStore';
import { useActStore } from '../actStore';
import { getGrowthHistory } from '../../services/api';

export function registerActHandlers(socket: Socket) {
  // New act started (game start or act transition)
  socket.on('act_started', (data: {
    session_id: number;
    act: { id: number; act_number: number; title: string; subtitle: string | null; started_at: string };
  }) => {
    console.log('Act started:', data);
    const actInfo: StoryActInfo = {
      id: data.act.id,
      actNumber: data.act.act_number,
      title: data.act.title,
      subtitle: data.act.subtitle,
      startedAt: data.act.started_at,
    };
    useActStore.getState().setCurrentAct(actInfo);
    useActStore.getState().setTransitioning(false);

    useGameStore.getState().addNotification({
      type: 'system',
      message: `${actInfo.actNumber}막 — ${actInfo.title} 시작`,
    });
  });

  // Act completed and transitioned to new act
  socket.on('act_completed', (data: {
    session_id: number;
    completed_act: { id: number; act_number: number; title: string; subtitle: string | null; started_at: string };
    new_act: { id: number; act_number: number; title: string; subtitle: string | null; started_at: string };
    growth_rewards: Array<{
      character_id: number;
      character_name: string;
      growth_type: string;
      growth_detail: Record<string, any>;
      narrative_reason: string;
    }>;
  }) => {
    console.log('Act completed:', data);

    const newAct: StoryActInfo = {
      id: data.new_act.id,
      actNumber: data.new_act.act_number,
      title: data.new_act.title,
      subtitle: data.new_act.subtitle,
      startedAt: data.new_act.started_at,
    };

    const rewards: GrowthReward[] = data.growth_rewards.map((r) => ({
      characterId: r.character_id,
      characterName: r.character_name,
      growthType: r.growth_type as GrowthReward['growthType'],
      growthDetail: r.growth_detail,
      narrativeReason: r.narrative_reason,
    }));

    useActStore.getState().setCurrentAct(newAct);
    useActStore.getState().setGrowthRewards(rewards);
    if (rewards.length > 0) {
      useActStore.getState().setShowGrowthModal(true);
    }

    useGameStore.getState().addNotification({
      type: 'system',
      message: `${data.completed_act.act_number}막 완료! ${newAct.actNumber}막 — ${newAct.title} 시작`,
    });

    // 성장 기록 갱신
    getGrowthHistory(data.session_id)
      .then((history) => useActStore.getState().setGrowthHistory(history))
      .catch((err) => console.error('Failed to load growth history:', err));
  });

  // Character growth applied (per character notification)
  socket.on('character_growth_applied', (data: {
    session_id: number;
    character_id: number;
    growth: {
      growth_type: string;
      growth_detail: Record<string, any>;
      narrative_reason: string;
    };
  }) => {
    console.log('Character growth applied:', data);
    const currentCharacter = useGameStore.getState().currentCharacter;
    if (currentCharacter && currentCharacter.id === data.character_id) {
      window.dispatchEvent(new CustomEvent('character_data_updated', {
        detail: { character_id: data.character_id },
      }));
    }
  });
}
