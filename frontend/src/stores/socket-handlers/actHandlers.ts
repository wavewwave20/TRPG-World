import type { Socket } from 'socket.io-client';
import type { StoryActInfo, GrowthReward } from '../../types/act';
import { useGameStore } from '../gameStore';
import { useAuthStore } from '../authStore';
import { useActStore } from '../actStore';
import { getCharacter, getGrowthHistory } from '../../services/api';

export function registerActHandlers(socket: Socket) {
  socket.on('act_transition_started', (data: {
    session_id: number;
    completed_act?: { act_number: number; title: string };
  }) => {
    console.log('Act transition started:', data);

    const gameState = useGameStore.getState();
    const userId = useAuthStore.getState().userId;
    const hostUserId = gameState.currentSession?.hostUserId;
    const isHost: boolean | null = (userId != null && hostUserId != null) ? hostUserId === userId : null;

    if (isHost === false) {
      // 참가자는 호스트 전용 대기 버튼 상태를 만들지 않음
      return;
    }

    const actState = useActStore.getState();
    const currentAct = actState.currentAct;

    // 버튼을 즉시 노출하기 위한 placeholder pending transition
    if (!actState.pendingTransition && currentAct) {
      actState.setPendingTransition({
        newAct: {
          id: -1,
          actNumber: currentAct.actNumber + 1,
          title: '다음 막',
          subtitle: null,
          startedAt: new Date().toISOString(),
        },
        rewards: [],
      });
    }

    actState.setTransitionCompletedTitle(null);
    if (!actState.isTransitioning) {
      actState.setTransitioning(false);
    }
  });

  socket.on('act_transition_cancelled', () => {
    useActStore.getState().setTransitionCompletedTitle(null);
    useActStore.getState().setTransitioning(false);
  });

  socket.on('act_transition_display_start', (data: { session_id: number }) => {
    console.log('Act transition display start:', data);
    useActStore.getState().runPendingTransition();
  });

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

    const actState = useActStore.getState();
    // 모든 플레이어가 동일한 pending 전환 상태를 보유.
    // 실제 모달/적용 시작은 호스트 버튼 -> 브로드캐스트 이벤트로 동기화.
    // 이미 전환 모달이 진행 중이면 리셋하지 않음 (호스트가 먼저 클릭한 경우)
    if (!actState.isTransitioning) {
      actState.setTransitionCompletedTitle(null);
    }
    actState.setPendingTransition({ newAct, rewards });

    useGameStore.getState().addNotification({
      type: 'system',
      message: `${data.completed_act.act_number}막 완료. ${newAct.actNumber}막 준비됨 (호스트 전환 버튼 대기)`,
    });

    // 성장 기록 갱신
    getGrowthHistory(data.session_id)
      .then((history) => useActStore.getState().setGrowthHistory(history))
      .catch((err) => console.error('Failed to load growth history:', err));
  });

  // Character growth applied (per character notification)
  socket.on('character_growth_applied', async (data: {
    session_id: number;
    character_id: number;
    growth: {
      growth_type: string;
      growth_detail: Record<string, any>;
      narrative_reason: string;
    };
  }) => {
    console.log('Character growth applied:', data);

    const gameState = useGameStore.getState();
    const currentCharacter = gameState.currentCharacter;
    const selectedParticipant = gameState.selectedParticipant;

    const shouldRefreshCurrent = !!currentCharacter && currentCharacter.id === data.character_id;
    const shouldRefreshSelected = !!selectedParticipant?.character && selectedParticipant.character.id === data.character_id;

    if (!shouldRefreshCurrent && !shouldRefreshSelected) {
      return;
    }

    try {
      const refreshed = await getCharacter(data.character_id);

      if (shouldRefreshCurrent) {
        useGameStore.getState().setCharacter(refreshed);
      }

      if (shouldRefreshSelected && selectedParticipant) {
        useGameStore.getState().setSelectedParticipant({
          ...selectedParticipant,
          character: refreshed,
        });
      }

      // participants 캐시에도 반영
      const participants = useGameStore.getState().participants;
      const nextParticipants = participants.map((p) =>
        p.character_id === data.character_id ? { ...p, character: refreshed } : p
      );
      useGameStore.getState().setParticipants(nextParticipants);
    } catch (err) {
      console.error('Failed to refresh character after growth:', err);
    }
  });
}
