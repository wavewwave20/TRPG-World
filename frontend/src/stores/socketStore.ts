import { create } from 'zustand';
import { io, Socket } from 'socket.io-client';
import { useGameStore } from './gameStore';
import { useActionStore } from './actionStore';
import { useStoryStore } from './storyStore';
import { useChatStore } from './chatStore';
import { useAuthStore } from './authStore';
import { useAIStore } from './aiStore';
import type { JudgmentSetup, JudgmentResult } from './aiStore';

interface SocketStore {
  socket: Socket | null;
  connected: boolean;
  error: string | null;
  connect: () => void;
  disconnect: () => void;
  emit: (event: string, data: any) => void;
  on: (event: string, handler: (data: any) => void) => void;
  off: (event: string, handler?: (data: any) => void) => void;
  joinSession: (sessionId: number, userId: number, characterId: number) => void;
  leaveSession: (sessionId: number, userId: number) => void;
}

export const useSocketStore = create<SocketStore>((set, get) => ({
  socket: null,
  connected: false,
  error: null,
  
  connect: () => {
    const socket = io('http://localhost:8000', {
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5
    });
    
    socket.on('connect', () => {
      console.log('Socket connected');
      set({ connected: true, error: null });

      // Auto rejoin current session on reconnect
      const session = useGameStore.getState().currentSession;
      const userId = useAuthStore.getState().userId;
      const character = useGameStore.getState().currentCharacter;
      if (session && userId && character) {
        try {
          get().emit('join_session', { 
            session_id: session.id, 
            user_id: userId,
            character_id: character.id
          });
        } catch (e) {
          console.warn('Failed to auto rejoin session:', e);
        }
      }
    });
    
    socket.on('disconnect', (reason) => {
      console.log('Socket disconnected:', reason);
      set({ connected: false });
    });
    
    socket.on('connect_error', (error) => {
      console.error('Socket connection error:', error);
      set({ 
        connected: false, 
        error: `Connection failed: ${error.message}` 
      });
    });
    
    socket.on('error', (error) => {
      console.error('Socket error:', error);
      const errorMessage = typeof error === 'string' ? error : error.message || 'An error occurred';
      set({ error: `Socket error: ${errorMessage}` });
      
      // Add error notification to gameStore
      useGameStore.getState().addError(errorMessage);
    });
    
    // Set up user_joined event listener
    socket.on('user_joined', (data: { 
      user_id: number, 
      session_id?: number, 
      character_name?: string,
      participants?: Array<{ user_id: number, character_id: number, character_name: string }>,
      participant_count?: number
    }) => {
      console.log('User joined:', data);
      
      // Update participants list if provided
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
    
    // Set up user_left event listener
    socket.on('user_left', (data: { 
      user_id: number, 
      session_id?: number, 
      character_name?: string,
      participants?: Array<{ user_id: number, character_id: number, character_name: string }>,
      participant_count?: number
    }) => {
      console.log('User left:', data);
      
      // Update participants list if provided
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
    
    // Set up action_submitted event listener
    // NOTE: Action text is intentionally NOT displayed in the notification
    // to maintain privacy until the judgment phase (Requirements 1.1, 1.2)
    socket.on('action_submitted', (data: { 
      action: { 
        id: number; 
        player_id: number; 
        character_name: string; 
        action_text: string; 
        order: number; 
      }; 
      queue_count: number 
    }) => {
      // Log without exposing action text for privacy
      console.log('Action submitted:', {
        action_id: data.action.id,
        character_name: data.action.character_name,
        queue_count: data.queue_count
      });
      
      // Update queue count in actionStore
      useActionStore.getState().setQueueCount(data.queue_count);
      
      // Add notification to gameStore
      // Only show character name, not action text (privacy requirement)
      useGameStore.getState().addNotification({
        type: 'action_submitted',
        message: `${data.action.character_name} 이(가) 행동을 제출했습니다`,
        characterName: data.action.character_name
      });
    });
    
    // Set up queue_updated event listener
    socket.on('queue_updated', (data: { 
      actions: any[]; 
      queue_count?: number 
    }) => {
      console.log('Queue updated:', data);
      
      // Update queue count in actionStore
      const queueCount = data.queue_count !== undefined ? data.queue_count : data.actions.length;
      useActionStore.getState().setQueueCount(queueCount);
    });
    
    // Set up story_committed event listener
    socket.on('story_committed', (data: { 
      story_entry: { 
        id: number; 
        role: 'USER' | 'AI'; 
        content: string; 
        created_at: string; 
      } 
    }) => {
      console.log('Story committed:', data);
      
      // Add story entry to storyStore
      useStoryStore.getState().addEntry(data.story_entry);
      
      // Re-enable action input
      useActionStore.getState().setActionInputDisabled(false);
      
      // Add notification to gameStore
      useGameStore.getState().addNotification({
        type: 'story_committed',
        message: '이야기가 진행됩니다.'
      });
    });

    // Set up chat_message event listener (ephemeral general chat)
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
    
    // Session ended broadcast -> alert system message
    socket.on('session_ended', (data: { session_id: number; reason?: string }) => {
      try {
        useGameStore.getState().addNotification({
          type: 'alert',
          message: '세션이 종료되었습니다.',
          sessionId: (data as any)?.session_id,
          autoHide: false,
        });
        // Clear judgments when session ends
        useAIStore.getState().clearJudgments();
      } catch {}
    });

    // AI Generation Events
    
    // AI generation started - show loading indicator
    socket.on('ai_generation_started', (data: { phase?: 'judgment' | 'narrative'; session_id?: number }) => {
      console.log('AI generation started:', data);
      
      // Only show loading for narrative phase (Phase 3)
      // Phase 1 (judgment) will show JudgmentPanel instead
      if (data.phase === 'narrative') {
        useAIStore.getState().setGenerating(true);
        useAIStore.getState().clearCurrentNarrative();
        
        useGameStore.getState().addNotification({
          type: 'system',
          message: 'AI가 스토리를 생성하고 있습니다...'
        });
      } else if (data.phase === 'judgment') {
        // Phase 1: Just show notification, no loading indicator
        useGameStore.getState().addNotification({
          type: 'system',
          message: 'AI가 판정을 준비하고 있습니다...'
        });
      }
    });
    
    // Judgment ready - receive single judgment setup for the player
    // Backend sends this to the player who submitted the action
    socket.on('judgment_ready', (data: { 
      session_id: number;
      character_id: number;
      judgment_id: number;
      action_text: string;
      modifier: number;
      difficulty: number;
      difficulty_reasoning: string;
    }) => {
      console.log('Judgment ready:', data);
      
      // Get current character to check if this is for us
      const currentCharacter = useGameStore.getState().currentCharacter;
      
      // Create judgment setup from the received data
      const judgmentSetup: JudgmentSetup = {
        action_id: data.judgment_id,
        character_id: data.character_id,
        character_name: currentCharacter?.name || `Character ${data.character_id}`,
        action_text: data.action_text,
        ability_score: 'dex', // Default, could be enhanced
        modifier: data.modifier,
        difficulty: data.difficulty,
        difficulty_reasoning: data.difficulty_reasoning,
        status: 'active',
        order: 0
      };
      
      // Add to existing judgments or create new list
      const currentJudgments = useAIStore.getState().judgments;
      const existingIndex = currentJudgments.findIndex(j => j.action_id === data.judgment_id);
      
      if (existingIndex === -1) {
        useAIStore.getState().setJudgmentSetups([...currentJudgments, judgmentSetup]);
      }
      
      // Hide loading indicator - Phase 1 is complete for this player
      useAIStore.getState().setGenerating(false);
      
      // Re-enable action input after judgment is ready
      useActionStore.getState().setActionInputDisabled(false);
      
      useGameStore.getState().addNotification({
        type: 'system',
        message: '판정이 준비되었습니다. 주사위를 굴려주세요!'
      });
    });
    
    // Player action analyzed - broadcast to other players (including host)
    // This event is sent to all participants except the action submitter
    socket.on('player_action_analyzed', (data: {
      session_id: number;
      character_id: number;
      character_name: string;
      judgment_id: number;
      action_text: string;
      modifier: number;
      difficulty: number;
      difficulty_reasoning: string;
    }) => {
      console.log('Player action analyzed:', data);
      
      // Create judgment setup from the received data (for other players to see)
      const judgmentSetup: JudgmentSetup = {
        action_id: data.judgment_id,
        character_id: data.character_id,
        character_name: data.character_name,
        action_text: data.action_text,
        ability_score: 'dex', // Default
        modifier: data.modifier,
        difficulty: data.difficulty,
        difficulty_reasoning: data.difficulty_reasoning,
        status: 'waiting', // Waiting for the player to roll dice
        order: useAIStore.getState().judgments.length
      };
      
      // Add to existing judgments
      const currentJudgments = useAIStore.getState().judgments;
      const existingIndex = currentJudgments.findIndex(j => j.action_id === data.judgment_id);
      
      if (existingIndex === -1) {
        useAIStore.getState().setJudgmentSetups([...currentJudgments, judgmentSetup]);
      }
      
      // Hide loading indicator - Phase 1 is complete
      useAIStore.getState().setGenerating(false);
      
      // Notify other players that someone submitted an action
      useGameStore.getState().addNotification({
        type: 'system',
        message: `${data.character_name}이(가) 행동을 제출했습니다. (DC ${data.difficulty})`
      });
    });
    
    // Next judgment - move to next judgment in sequence
    socket.on('next_judgment', (data: { judgment_index: number }) => {
      console.log('Next judgment:', data);

      // If this client requires local confirmation, hold the next index until user clicks
      const aiStateBefore = useAIStore.getState();
      if (aiStateBefore.ackRequiredForActionId !== null) {
        useAIStore.getState().setPendingNextIndex(data.judgment_index);
        return;
      }

      // Otherwise, transition immediately for observers
      useAIStore.getState().setCurrentJudgmentIndex(data.judgment_index);
      
      // Update judgment statuses: mark previous as complete, current as active
      const aiState = useAIStore.getState();
      const updatedJudgments = aiState.judgments.map((judgment, index) => {
        if (index < data.judgment_index) {
          return { ...judgment, status: 'complete' as 'complete' };
        } else if (index === data.judgment_index) {
          return { ...judgment, status: 'active' as 'active' };
        } else {
          return { ...judgment, status: 'waiting' as 'waiting' };
        }
      });
      
      useAIStore.setState({ judgments: updatedJudgments });
    });
    
    // Dice rolling - show animation to all participants
    socket.on('dice_rolling', (data: { action_id: number }) => {
      console.log('Dice rolling:', data);
      
      // Update judgment status to 'rolling'
      useAIStore.getState().setJudgmentRolling(data.action_id);
    });
    
    // Dice rolled - show result to all participants
    // Backend format: session_id, character_id, character_name, judgment_id, dice_result, modifier, final_value, difficulty, outcome
    socket.on('dice_rolled', (data: { 
      session_id: number;
      character_id: number;
      character_name: string;
      judgment_id: number;
      dice_result: number;
      modifier: number;
      final_value: number;
      difficulty: number;
      outcome: 'critical_failure' | 'failure' | 'success' | 'critical_success';
    }) => {
      console.log('Dice rolled:', data);
      
      // Update judgment with result and mark as complete
      useAIStore.getState().updateJudgmentResult(data.judgment_id, {
        dice_result: data.dice_result,
        final_value: data.final_value,
        outcome: data.outcome,
        outcome_reasoning: `주사위 ${data.dice_result} + 보정치 ${data.modifier} = ${data.final_value} vs DC ${data.difficulty}`,
        status: 'complete'
      });
      try {
        useAIStore.getState().setLastDiceRolledAt(Date.now());
        const myChar = useGameStore.getState().currentCharacter;
        if (myChar && myChar.id === data.character_id) {
          useAIStore.getState().setAckRequired(data.judgment_id);
        }
      } catch {}
      
      // Show outcome notification
      const outcomeText = {
        critical_failure: '대실패!',
        failure: '실패',
        success: '성공',
        critical_success: '대성공!'
      }[data.outcome];
      
      useGameStore.getState().addNotification({
        type: 'system',
        message: `${data.character_name}: 주사위 ${data.dice_result} (${outcomeText})`
      });
    });
    
    // All dice rolled - all players have rolled, Phase 3 will start
    socket.on('all_dice_rolled', (data: { session_id: number }) => {
      console.log('All dice rolled:', data);
      
      useGameStore.getState().addNotification({
        type: 'system',
        message: '모든 플레이어가 주사위를 굴렸습니다. 스토리가 생성됩니다...'
      });
    });
    
    // Story generation started - Phase 3 begins
    socket.on('story_generation_started', (data: { session_id: number }) => {
      console.log('Story generation started:', data);
      
      useAIStore.getState().setGenerating(true);
      useAIStore.getState().clearCurrentNarrative();
      
      useGameStore.getState().addNotification({
        type: 'system',
        message: 'AI가 스토리를 생성하고 있습니다...'
      });
    });
    
    // Narrative token - append to current narrative
    socket.on('narrative_token', (data: { token: string }) => {
      useAIStore.getState().appendNarrativeToken(data.token);
    });
    
    // Story generation complete - Phase 3 finished
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
      console.log('Story generation complete:', data);
      
      useAIStore.getState().setGenerating(false);
      
      // Add narrative to story store (create a temporary story entry)
      // The actual story entry will be loaded from the database via story_committed event
      // But we show it immediately for better UX
      if (data.narrative) {
        const tempEntry = {
          id: Date.now(), // Temporary ID
          role: 'AI' as 'AI',
          content: data.narrative,
          created_at: new Date().toISOString()
        };
        useStoryStore.getState().addEntry(tempEntry);
      }
      
      // Clear judgments after story is complete (ready for next round)
      useAIStore.getState().clearJudgments();
      
      // Re-enable action input for next round
      useActionStore.getState().setActionInputDisabled(false);
      
      useGameStore.getState().addNotification({
        type: 'system',
        message: '스토리 생성이 완료되었습니다.'
      });
    });
    
    // AI generation complete (legacy event) - hide loading indicator
    socket.on('ai_generation_complete', (data: { 
      story_log_id?: number;
      narrative?: string;
    }) => {
      console.log('AI generation complete:', data);
      
      useAIStore.getState().setGenerating(false);
      
      // Save judgments to history if story_log_id is provided
      if (data.story_log_id) {
        const completedJudgments = useAIStore.getState().judgments.filter(
          (j): j is JudgmentResult => 'dice_result' in j
        );
        useAIStore.getState().saveJudgmentsToHistory(data.story_log_id, completedJudgments);
      }
      
      useGameStore.getState().addNotification({
        type: 'system',
        message: 'AI 생성이 완료되었습니다.'
      });
    });
    
    // AI generation error - show error message
    socket.on('ai_generation_error', (data: { 
      error: string;
      phase?: 'judgment' | 'narrative';
    }) => {
      console.error('AI generation error:', data);
      
      useAIStore.getState().setGenerating(false);
      
      // Display error notification with auto-dismiss after 10 seconds
      useGameStore.getState().addError(data.error, 10000);
      
      useGameStore.getState().addNotification({
        type: 'error',
        message: `AI 생성 오류: ${data.error}`,
        autoHide: true
      });
    });

    set({ socket });
  },
  
  disconnect: () => {
    const { socket } = get();
    if (socket) {
      socket.disconnect();
      set({ socket: null, connected: false, error: null });
    }
  },
  
  emit: (event: string, data: any) => {
    const { socket } = get();
    if (socket && socket.connected) {
      socket.emit(event, data);
    } else {
      console.warn(`Cannot emit event "${event}": socket not connected`);
    }
  },
  
  on: (event: string, handler: (data: any) => void) => {
    const { socket } = get();
    if (socket) {
      socket.on(event, handler);
    }
  },
  
  off: (event: string, handler?: (data: any) => void) => {
    const { socket } = get();
    if (socket) {
      if (handler) {
        socket.off(event, handler);
      } else {
        socket.off(event);
      }
    }
  },
  
  // Join a game session room
  joinSession: (sessionId: number, userId: number, characterId: number) => {
    const { emit } = get();
    emit('join_session', { 
      session_id: sessionId, 
      user_id: userId,
      character_id: characterId
    });
  },
  
  // Leave a game session room
  leaveSession: (sessionId: number, userId: number) => {
    const { emit } = get();
    emit('leave_session', { session_id: sessionId, user_id: userId });
  }
}));

