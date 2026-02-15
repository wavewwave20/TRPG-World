import type { Socket } from 'socket.io-client';
import { useGameStore } from '../gameStore';
import { useActionStore } from '../actionStore';
import { useStoryStore } from '../storyStore';
import { useChatStore } from '../chatStore';

export function registerSessionHandlers(socket: Socket) {
  socket.on('user_joined', (data: {
    user_id: number;
    session_id?: number;
    character_name?: string;
    participants?: Array<{ user_id: number; character_id: number; character_name: string }>;
    participant_count?: number;
  }) => {
    if (data.participants) {
      useGameStore.getState().setParticipants(data.participants);
    }
    useGameStore.getState().addNotification({
      type: 'user_joined',
      message: `${data.character_name ?? 'User ' + data.user_id} 이(가) 파티에 참여했습니다.`,
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
    if (data.participants) {
      useGameStore.getState().setParticipants(data.participants);
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
    queue_count: number;
  }) => {
    useActionStore.getState().setQueueCount(data.queue_count);
    useGameStore.getState().addNotification({
      type: 'action_submitted',
      message: `${data.action.character_name} 이(가) 행동을 제출했습니다`,
      characterName: data.action.character_name,
    });
  });

  socket.on('queue_updated', (data: {
    actions: Array<{ id: number; player_id: number; character_name: string; action_text: string; order: number }>;
    queue_count?: number;
  }) => {
    const queueCount = data.queue_count !== undefined ? data.queue_count : data.actions.length;
    useActionStore.getState().setQueueCount(queueCount);
  });

  socket.on('story_committed', (data: {
    story_entry: { id: number; role: 'USER' | 'AI'; content: string; created_at: string };
  }) => {
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
    useChatStore.getState().addMessage({
      session_id: data.session_id,
      user_id: data.user_id ?? null,
      character_name: data.character_name,
      message: data.message,
    });
  });
}
