import type { Socket } from 'socket.io-client';
import type { JudgmentResult } from '../../types/judgment';
import { useGameStore } from '../gameStore';
import { useActionStore } from '../actionStore';
import { useStoryStore } from '../storyStore';
import { useAIStore } from '../aiStore';

export function registerNarrativeHandlers(socket: Socket) {
  // AI generation started - show loading indicator
  socket.on('ai_generation_started', (data: { phase?: 'judgment' | 'narrative'; session_id?: number }) => {
    console.log('AI generation started:', data);

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
  socket.on('narrative_stream_started', (data: { session_id: number }) => {
    console.log('Narrative stream started:', data);
    useAIStore.getState().setGenerating(true);
    useAIStore.getState().clearCurrentNarrative();
    useGameStore.getState().setJudgmentModalOpen(false);
    useGameStore.getState().addNotification({
      type: 'system',
      message: '이야기가 시작됩니다...',
    });
  });

  // Narrative token - append to current narrative
  socket.on('narrative_token', (data: { token: string; session_id?: number }) => {
    console.log('Narrative token received:', data.token);
    useAIStore.getState().appendNarrativeToken(data.token);
  });

  // Narrative complete (streaming finished)
  socket.on('narrative_complete', (data: { session_id: number }) => {
    console.log('Narrative complete:', data);
    useAIStore.getState().setGenerating(false);
    useAIStore.getState().clearJudgments();
    useAIStore.getState().clearCurrentNarrative();
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

  // --- LEGACY events (backward compatibility) ---

  socket.on('story_generation_started', (data: { session_id: number }) => {
    console.log('Story generation started (legacy):', data);
    useAIStore.getState().setGenerating(true);
    useAIStore.getState().clearCurrentNarrative();
    useGameStore.getState().addNotification({
      type: 'system',
      message: 'AI가 스토리를 생성하고 있습니다...',
    });
  });

  socket.on('story_generation_complete', (data: {
    session_id: number;
    narrative: string;
    judgments: Array<{
      character_id: number;
      action_text: string;
      dice_result: number;
      modifier: number;
      final_value: number;
      difficulty: number;
      difficulty_reasoning?: string;
      outcome: string;
    }>;
  }) => {
    console.log('Story generation complete (legacy):', data);
    useAIStore.getState().setGenerating(false);
    if (data.narrative) {
      useStoryStore.getState().addEntry({
        id: Date.now(),
        role: 'AI' as const,
        content: data.narrative,
        created_at: new Date().toISOString(),
      });
    }
    useAIStore.getState().clearJudgments();
    useActionStore.getState().setActionInputDisabled(false);
    useGameStore.getState().addNotification({
      type: 'system',
      message: '스토리 생성이 완료되었습니다.',
    });
  });

  socket.on('ai_generation_complete', (data: {
    story_log_id?: number;
    narrative?: string;
  }) => {
    console.log('AI generation complete:', data);
    useAIStore.getState().setGenerating(false);
    if (data.story_log_id) {
      const completedJudgments = useAIStore.getState().judgments.filter(
        (j): j is JudgmentResult => 'dice_result' in j
      );
      useAIStore.getState().saveJudgmentsToHistory(data.story_log_id, completedJudgments);
    }
    useGameStore.getState().addNotification({
      type: 'system',
      message: 'AI 생성이 완료되었습니다.',
    });
  });

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
}
