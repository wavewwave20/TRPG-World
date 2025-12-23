import { useEffect } from 'react';
import LeftPane from './LeftPane';
import CenterPane from './CenterPane';
import RightPane from './RightPane';
import JudgmentModal from './JudgmentModal';
import { useGameStore } from '../stores/gameStore';
import { useAuthStore } from '../stores/authStore';
import { useSocketStore } from '../stores/socketStore';
import { useChatStore } from '../stores/chatStore';

export default function GameLayout() {
  const currentSession = useGameStore((state) => state.currentSession);
  const setSession = useGameStore((state) => state.setSession);
  const addNotification = useGameStore((state) => state.addNotification);
  const clearNotifications = useGameStore((state) => state.clearNotifications);
  const isJudgmentModalOpen = useGameStore((state) => state.isJudgmentModalOpen);
  const setJudgmentModalOpen = useGameStore((state) => state.setJudgmentModalOpen);
  const userId = useAuthStore((state) => state.userId);
  const emit = useSocketStore((state) => state.emit);
  const socket = useSocketStore((state) => state.socket);
  const clearChat = useChatStore((state) => state.clear);

  // Session heartbeat: every 5s while inside a session page
  useEffect(() => {
    if (!currentSession || !userId) return;

    // Send an immediate heartbeat on mount
    emit('session_heartbeat', { session_id: currentSession.id, user_id: userId });

    const interval = setInterval(() => {
      emit('session_heartbeat', { session_id: currentSession.id, user_id: userId });
    }, 5000);

    return () => {
      clearInterval(interval);
    };
  }, [currentSession, userId, emit]);

  // Handle session_ended event
  useEffect(() => {
    if (!socket || !currentSession) return;

    const handleSessionEnded = (data: { 
      session_id: number; 
      reason: string;
    }) => {
      // Only handle if it's for the current session
      if (currentSession.id !== data.session_id) return;

      // Show notification with reason
      const reasonText = data.reason === 'host_disconnected'
        ? '호스트가 연결을 끊었습니다'
        : '모든 참가자가 나갔습니다';

      addNotification({
        type: 'alert',
        message: `세션이 종료되었습니다: ${reasonText}`,
        autoHide: false,
      });

      // Clear session state (but keep character selection)
      clearChat();
      clearNotifications();
      setSession(null);
      // Note: Don't clear character here - character selection should persist
      // across sessions so users can rejoin or join other sessions

      // Note: Redirect to session list is handled by App.tsx
      // When currentSession becomes null, showLobby becomes true
    };

    socket.on('session_ended', handleSessionEnded);

    return () => {
      socket.off('session_ended', handleSessionEnded);
    };
  }, [socket, currentSession, addNotification, clearChat, clearNotifications, setSession]);

  // Handle judgment modal open/close based on WebSocket events
  // Task 13: WebSocket event handler updates
  // Requirement 1.1: Open modal when judgment phase starts
  // Requirement 1.5: Auto-close when story generation starts
  // Requirement 8.1, 8.4, 8.5: Use existing WebSocket event handlers
  // Requirement 9.1: Modal controls left pane state
  useEffect(() => {
    if (!socket || !currentSession) return;

    // Open modal when judgment phase starts
    // The judgment phase starts when either:
    // 1. judgment_ready - for the player who submitted the action
    // 2. player_action_analyzed - for other players observing
    const handleJudgmentReady = () => {
      console.log('[GameLayout] Opening judgment modal (judgment_ready)');
      setJudgmentModalOpen(true);
    };

    const handlePlayerActionAnalyzed = () => {
      console.log('[GameLayout] Opening judgment modal (player_action_analyzed)');
      setJudgmentModalOpen(true);
    };

    // Close modal when story generation starts (Phase 3)
    // This signals that all judgments are complete
    const handleStoryGenerationStarted = () => {
      console.log('[GameLayout] Closing judgment modal (story_generation_started)');
      setJudgmentModalOpen(false);
    };

    // Register event handlers
    socket.on('judgment_ready', handleJudgmentReady);
    socket.on('player_action_analyzed', handlePlayerActionAnalyzed);
    socket.on('story_generation_started', handleStoryGenerationStarted);

    // Cleanup on unmount
    return () => {
      socket.off('judgment_ready', handleJudgmentReady);
      socket.off('player_action_analyzed', handlePlayerActionAnalyzed);
      socket.off('story_generation_started', handleStoryGenerationStarted);
    };
  }, [socket, currentSession, setJudgmentModalOpen]);

  return (
    <>
      <div className="h-full w-full grid grid-cols-12 gap-6 p-6">
        {/* Left: Character Status (25%) */}
        <div className="col-span-3 bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
          <LeftPane />
        </div>
        
        {/* Center: Story View (50%) */}
        <div className="col-span-6 bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col relative">
          <CenterPane />
        </div>
        
        {/* Right: Chat (25%) */}
        <div className="col-span-3 border border-slate-200 bg-white rounded-xl shadow-sm overflow-hidden flex flex-col">
          <RightPane />
        </div>
      </div>

      {/* Judgment Modal */}
      <JudgmentModal
        isOpen={isJudgmentModalOpen}
        onClose={() => setJudgmentModalOpen(false)}
        sessionId={currentSession?.id || 0}
      />
    </>
  );
}
