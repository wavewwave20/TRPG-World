import type { Socket } from 'socket.io-client';
import { useGameStore } from '../gameStore';
import { useActionStore } from '../actionStore';
import { useAIStore } from '../aiStore';
import { useStoryImageStore } from '../storyImageStore';

export function registerNarrativeHandlers(socket: Socket) {
  // AI generation started - show loading indicator
  socket.on('ai_generation_started', (data: { phase?: 'judgment' | 'narrative'; session_id?: number }) => {
    if (data.phase === 'narrative') {
      useAIStore.getState().setGenerating(true);
      useAIStore.getState().clearCurrentNarrative();
      useGameStore.getState().addNotification({
        type: 'system',
        message: 'AI가 스토리를 생성하고 있습니다...',
      });
    } else if (data.phase === 'judgment') {
      useGameStore.getState().addNotification({
        type: 'system',
        message: 'AI가 판정을 준비하고 있습니다...',
      });
    }
  });

  // Narrative stream started
  socket.on('narrative_stream_started', (data: { session_id?: number; event_triggered?: boolean }) => {
    useAIStore.getState().setGenerating(true);
    useAIStore.getState().clearCurrentNarrative();
    if (data?.event_triggered) {
      useAIStore.getState().setEventTriggered(true);
    }
    useGameStore.getState().setJudgmentModalOpen(false);
    useGameStore.getState().addNotification({
      type: 'system',
      message: '이야기가 시작됩니다...',
    });
  });

  // Narrative token - append to current narrative
  socket.on('narrative_token', (data: { token: string; session_id?: number }) => {
    useAIStore.getState().appendNarrativeToken(data.token);
  });

  // Narrative complete (streaming finished)
  socket.on('narrative_complete', (data: { session_id: number }) => {
    useAIStore.getState().setGenerating(false);
    useActionStore.getState().setActionInputDisabled(false);
    window.dispatchEvent(new CustomEvent('story_logs_updated', { detail: { session_id: data.session_id } }));
    useGameStore.getState().addNotification({
      type: 'system',
      message: '이야기 생성이 완료되었습니다.',
    });
  });

  // Narrative error
  socket.on('narrative_error', (data: { session_id: number; error: string }) => {
    console.error('Narrative error:', data);
    useAIStore.getState().setGenerating(false);
    useGameStore.getState().addError(`이야기 생성 실패: ${data.error}`);
  });

  // Game start error
  socket.on('start_game_error', (data: { session_id: number; error: string }) => {
    console.error('Start game error:', data);
    useGameStore.getState().addError(`게임 시작 실패: ${data.error}`);
  });

  // Commit/phase errors before narrative streaming starts.
  socket.on('ai_generation_error', (data: {
    error: string;
    phase?: 'judgment' | 'narrative';
  }) => {
    console.error('AI generation error:', data);
    useAIStore.getState().setGenerating(false);
    useGameStore.getState().addError(data.error, 10000);
    useGameStore.getState().addNotification({
      type: 'error',
      message: `AI 생성 오류: ${data.error}`,
      autoHide: true,
    });
  });

  socket.on('story_image_generation_started', (data: { session_id: number; story_log_id: number }) => {
    const currentSessionId = useGameStore.getState().currentSession?.id;
    if (!currentSessionId || data.session_id !== currentSessionId) return;
    useStoryImageStore.getState().startGeneration(data.story_log_id);
  });

  socket.on('story_image_generated', (data: {
    session_id: number;
    story_log_id: number;
    image_url: string;
    model_id?: string;
  }) => {
    const currentSessionId = useGameStore.getState().currentSession?.id;
    if (!currentSessionId || data.session_id !== currentSessionId) return;
    useStoryImageStore.getState().setGenerated(data.story_log_id, data.image_url, data.model_id);
  });

  socket.on('story_image_generation_error', (data: {
    session_id: number;
    story_log_id: number;
    error: string;
  }) => {
    const currentSessionId = useGameStore.getState().currentSession?.id;
    if (!currentSessionId || data.session_id !== currentSessionId) return;
    useStoryImageStore.getState().setError(data.story_log_id, data.error);
    useGameStore.getState().addError(`이미지 생성 실패: ${data.error}`);
  });
}
