import type { Socket } from 'socket.io-client';
import type { JudgmentSetup } from '../../types/judgment';
import { resolveAbilityScore, computeRequiresRoll } from '../../utils/judgment';
import { useGameStore } from '../gameStore';
import { useActionStore } from '../actionStore';
import { useAIStore } from '../aiStore';

/** 서버에서 수신하는 judgment raw 데이터 */
interface RawJudgmentData {
  judgment_id: number;
  character_id: number;
  action_text: string;
  action_type?: string;
  modifier: number;
  difficulty: number;
  difficulty_reasoning: string;
  requires_roll?: boolean;
}

/** 서버 데이터를 JudgmentSetup으로 변환 */
function createJudgmentSetup(
  data: RawJudgmentData,
  characterName: string,
  status: 'active' | 'waiting',
  order: number
): JudgmentSetup {
  return {
    action_id: data.judgment_id,
    character_id: data.character_id,
    character_name: characterName,
    action_text: data.action_text,
    ability_score: resolveAbilityScore(data.action_type),
    modifier: data.modifier,
    difficulty: data.difficulty,
    difficulty_reasoning: data.difficulty_reasoning,
    status,
    order,
    requires_roll: computeRequiresRoll(data.difficulty, data.requires_roll),
  };
}

/** 판정을 기존 목록에 추가 (중복 방지) */
function addJudgmentIfNew(judgmentSetup: JudgmentSetup): void {
  const state = useAIStore.getState();
  const currentJudgments = state.judgments;
  const exists = currentJudgments.some((j) => j.action_id === judgmentSetup.action_id);
  if (!exists) {
    // Keep current index stable while appending new judgments.
    // Resetting index to 0 on every append can break multi-step progression.
    useAIStore.setState({
      judgments: [...currentJudgments, judgmentSetup],
      currentJudgmentIndex: currentJudgments.length === 0 ? 0 : state.currentJudgmentIndex,
    });
  }
}

export function registerJudgmentHandlers(socket: Socket) {
  // Judgment ready - receive single judgment setup for the player
  socket.on('judgment_ready', (data: RawJudgmentData & { session_id: number }) => {
    console.log('Judgment ready:', data);

    const currentCharacter = useGameStore.getState().currentCharacter;
    const characterName = currentCharacter?.name || `Character ${data.character_id}`;

    const judgmentSetup = createJudgmentSetup(data, characterName, 'active', 0);
    addJudgmentIfNew(judgmentSetup);

    useAIStore.getState().setGenerating(false);
    useActionStore.getState().setActionInputDisabled(false);

    useGameStore.getState().addNotification({
      type: 'system',
      message: judgmentSetup.requires_roll
        ? '판정이 준비되었습니다. 주사위를 굴려주세요!'
        : '판정이 준비되었습니다. 확인해주세요.',
    });
  });

  // Player action analyzed - broadcast to other players (including host)
  socket.on('player_action_analyzed', (data: RawJudgmentData & {
    session_id: number;
    character_name: string;
  }) => {
    console.log('Player action analyzed:', data);

    const judgmentSetup = createJudgmentSetup(
      data,
      data.character_name,
      'waiting',
      useAIStore.getState().judgments.length
    );
    addJudgmentIfNew(judgmentSetup);

    useAIStore.getState().setGenerating(false);

    useGameStore.getState().addNotification({
      type: 'system',
      message: `${data.character_name}이(가) 행동을 제출했습니다. (DC ${data.difficulty})`,
    });
  });

  // Next judgment - move to next judgment in sequence
  socket.on('next_judgment', (data: { judgment_index: number }) => {
    console.log('Next judgment:', data);

    const aiStateBefore = useAIStore.getState();
    if (aiStateBefore.ackRequiredForActionId !== null) {
      useAIStore.getState().setPendingNextIndex(data.judgment_index);
      return;
    }

    useAIStore.getState().setCurrentJudgmentIndex(data.judgment_index);

    const aiState = useAIStore.getState();
    const updatedJudgments = aiState.judgments.map((judgment, index) => {
      if (index < data.judgment_index) {
        return { ...judgment, status: 'complete' as const };
      } else if (index === data.judgment_index) {
        return { ...judgment, status: 'active' as const };
      } else {
        return { ...judgment, status: 'waiting' as const };
      }
    });
    useAIStore.setState({ judgments: updatedJudgments });
  });

  // Dice rolling - show animation to all participants
  socket.on('dice_rolling', (data: { action_id: number }) => {
    console.log('Dice rolling:', data);
    useAIStore.getState().setJudgmentRolling(data.action_id);
  });

  // Dice rolled - show result to all participants
  socket.on('dice_rolled', (data: {
    session_id: number;
    character_id: number;
    character_name: string;
    judgment_id: number;
    dice_result: number;
    modifier: number;
    final_value: number;
    difficulty: number;
    outcome: 'critical_failure' | 'failure' | 'success' | 'critical_success' | 'auto_success';
    requires_roll?: boolean;
  }) => {
    console.log('Dice rolled:', data);

    const isAutoSuccess = data.outcome === 'auto_success';

    useAIStore.getState().updateJudgmentResult(data.judgment_id, {
      dice_result: data.dice_result,
      final_value: data.final_value,
      outcome: data.outcome,
      outcome_reasoning: isAutoSuccess
        ? '위험이나 대립이 없는 행동으로, 자동으로 성공합니다.'
        : `주사위 ${data.dice_result} + 보정치 ${data.modifier} = ${data.final_value} vs DC ${data.difficulty}`,
      status: 'complete',
    });
    try {
      useAIStore.getState().setLastDiceRolledAt(Date.now());
      const myChar = useGameStore.getState().currentCharacter;
      if (myChar && myChar.id === data.character_id) {
        useAIStore.getState().setAckRequired(data.judgment_id);
      }
    } catch { /* ignore */ }

    const outcomeText: Record<string, string> = {
      critical_failure: '대실패!',
      failure: '실패',
      success: '성공',
      critical_success: '대성공!',
      auto_success: '자동 성공',
    };

    useGameStore.getState().addNotification({
      type: 'system',
      message: isAutoSuccess
        ? `${data.character_name}: 자동 성공`
        : `${data.character_name}: 주사위 ${data.dice_result} (${outcomeText[data.outcome] || data.outcome})`,
    });
  });

  // All dice rolled
  socket.on('all_dice_rolled', (data: { session_id: number }) => {
    console.log('All dice rolled:', data);
    useGameStore.getState().addNotification({
      type: 'system',
      message: '모든 플레이어가 주사위를 굴렸습니다. 스토리가 생성됩니다...',
    });
  });

  // Judgments ready - pre-rolling complete
  socket.on('judgments_ready', (data: {
    session_id: number;
    analyses: Array<{
      character_id: number;
      action_text: string;
      modifier: number;
      difficulty: number;
      difficulty_reasoning: string;
    }>;
  }) => {
    console.log('Judgments ready (pre-rolled):', data);
    useGameStore.getState().addNotification({
      type: 'system',
      message: '판정 준비 완료! 주사위를 확인하세요.',
    });
  });
}
