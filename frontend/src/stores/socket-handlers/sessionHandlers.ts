import type { Socket } from 'socket.io-client';
import { useGameStore } from '../gameStore';
import { useActionStore } from '../actionStore';
import { useStoryStore } from '../storyStore';
import { useChatStore } from '../chatStore';
import { useAuthStore } from '../authStore';
import { getCharacter } from '../../services/api';

interface SessionParticipantPayload {
  user_id: number;
  character_id: number;
  character_name: string;
}

function normalizeParticipants(participants: SessionParticipantPayload[]): SessionParticipantPayload[] {
  const byUser = new Map<number, SessionParticipantPayload>();
  for (const participant of participants) {
    byUser.set(participant.user_id, participant);
  }
  return Array.from(byUser.values()).sort((a, b) => a.user_id - b.user_id);
}

function isCurrentSessionEvent(sessionId?: number): boolean {
  const currentSessionId = useGameStore.getState().currentSession?.id;
  if (!currentSessionId) {
    return false;
  }
  if (sessionId != null && sessionId !== currentSessionId) {
    return false;
  }
  return true;
}

export function registerSessionHandlers(socket: Socket) {
  socket.on('user_joined', (data: {
    user_id: number;
    session_id?: number;
    character_name?: string;
    participants?: Array<{ user_id: number; character_id: number; character_name: string }>;
    participant_count?: number;
    reconnected?: boolean;
  }) => {
    if (!isCurrentSessionEvent(data.session_id)) {
      return;
    }

    if (data.participants) {
      useGameStore.getState().setParticipants(normalizeParticipants(data.participants));
    }

    const myUserId = useAuthStore.getState().userId;
    const isSelfReconnect = data.reconnected && myUserId === data.user_id;
    if (isSelfReconnect) {
      return;
    }

    const joinMessage = data.reconnected
      ? `${data.character_name ?? 'User ' + data.user_id} 이(가) 재접속했습니다.`
      : `${data.character_name ?? 'User ' + data.user_id} 이(가) 파티에 참여했습니다.`;

    useGameStore.getState().addNotification({
      type: 'user_joined',
      message: joinMessage,
      userId: data.user_id,
      sessionId: data.session_id,
    });
  });

  socket.on('user_left', (data: {
    user_id: number;
    session_id?: number;
    character_name?: string;
    participants?: Array<{ user_id: number; character_id: number; character_name: string }>;
    participant_count?: number;
  }) => {
    if (!isCurrentSessionEvent(data.session_id)) {
      return;
    }

    if (data.participants) {
      useGameStore.getState().setParticipants(normalizeParticipants(data.participants));
      const selectedParticipant = useGameStore.getState().selectedParticipant;
      if (selectedParticipant?.user_id === data.user_id) {
        useGameStore.getState().setSelectedParticipant(null);
      }
    }
    useGameStore.getState().addNotification({
      type: 'user_left',
      message: `${data.character_name ?? 'User ' + data.user_id} 이(가) 파티를 떠났습니다.`,
      userId: data.user_id,
      sessionId: data.session_id,
    });
  });

  // NOTE: Action text is intentionally NOT displayed in the notification
  // to maintain privacy until the judgment phase
  socket.on('action_submitted', (data: {
    action: {
      id: number;
      player_id: number;
      character_name: string;
      action_text: string;
      order: number;
    };
    session_id?: number;
    queue_count: number;
  }) => {
    if (!isCurrentSessionEvent(data.session_id)) {
      return;
    }
    useActionStore.getState().setQueueCount(data.queue_count);
    useGameStore.getState().addNotification({
      type: 'action_submitted',
      message: `${data.action.character_name} 이(가) 행동을 제출했습니다`,
      characterName: data.action.character_name,
    });
  });

  socket.on('queue_updated', (data: {
    session_id?: number;
    actions: Array<{ id: number; player_id: number; character_name: string; action_text: string; order: number }>;
    queue_count?: number;
  }) => {
    if (!isCurrentSessionEvent(data.session_id)) {
      return;
    }
    const queueCount = data.queue_count !== undefined ? data.queue_count : data.actions.length;
    useActionStore.getState().setQueueCount(queueCount);
  });

  socket.on('story_committed', (data: {
    story_entry: { id: number; role: 'USER' | 'AI'; content: string; created_at: string };
  }) => {
    const sessionId = (data.story_entry as { session_id?: number }).session_id;
    if (!isCurrentSessionEvent(sessionId)) {
      return;
    }
    useStoryStore.getState().addEntry(data.story_entry);
    useActionStore.getState().setActionInputDisabled(false);
    useGameStore.getState().addNotification({
      type: 'story_committed',
      message: '이야기가 진행됩니다.',
    });
  });

  socket.on('chat_message', (data: {
    session_id: number;
    user_id: number | null;
    character_name?: string;
    message: string;
  }) => {
    if (!isCurrentSessionEvent(data.session_id)) {
      return;
    }
    useChatStore.getState().addMessage({
      session_id: data.session_id,
      user_id: data.user_id ?? null,
      character_name: data.character_name,
      message: data.message,
    });
  });

  socket.on('character_state_updated', async (data: {
    session_id: number;
    character_id: number;
    reason?: string;
  }) => {
    if (!isCurrentSessionEvent(data.session_id)) {
      return;
    }

    const state = useGameStore.getState();
    const currentCharacter = state.currentCharacter;
    const selectedParticipant = state.selectedParticipant;

    const shouldRefreshCurrent = !!currentCharacter && currentCharacter.id === data.character_id;
    const shouldRefreshSelected = !!selectedParticipant?.character && selectedParticipant.character.id === data.character_id;
    const shouldRefreshParticipants = state.participants.some((p) => p.character_id === data.character_id);

    if (!shouldRefreshCurrent && !shouldRefreshSelected && !shouldRefreshParticipants) {
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

      const participants = useGameStore.getState().participants;
      const nextParticipants = participants.map((participant) =>
        participant.character_id === data.character_id
          ? { ...participant, character: refreshed }
          : participant
      );
      useGameStore.getState().setParticipants(nextParticipants);
    } catch (error) {
      console.error('Failed to refresh character after state update', error);
    }
  });
}
