import { useEffect, useState } from 'react';
import { useSocketStore } from './stores/socketStore';
import { useChatStore } from './stores/chatStore';
import { useGameStore } from './stores/gameStore';
import { useAuthStore } from './stores/authStore';
import GameLayout from './components/GameLayout';
import SessionCreationForm from './components/SessionCreationForm';
import SessionList from './components/SessionList';
import HostSessionsManager from './components/HostSessionsManager';
import LoginForm from './components/LoginForm';
import CharacterManagement from './components/CharacterManagement';
import type { Character as BaseCharacter } from './types/character';
import './App.css'

interface Character extends BaseCharacter {
  user_id: number;
  created_at: string;
}

function App() {
  const { connect, disconnect, connected, error } = useSocketStore();
  const currentSession = useGameStore((state) => state.currentSession);
  const setCharacter = useGameStore((state) => state.setCharacter);
  const setSession = useGameStore((state) => state.setSession);
  const clearNotifications = useGameStore((state) => state.clearNotifications);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const userId = useAuthStore((state) => state.userId);
  const leaveSessionSock = useSocketStore((state) => state.leaveSession);
  const clearChat = useChatStore((state) => state.clear);
  
  const [showLobby, setShowLobby] = useState(true);
  const [selectedCharacter, setSelectedCharacter] = useState<Character | null>(null);

  useEffect(() => {
    // Initialize socket connection on mount if authenticated
    if (isAuthenticated) {
      connect();
    }
    
    // Cleanup: disconnect on unmount
    return () => {
      disconnect();
    };
  }, [connect, disconnect, isAuthenticated]);

  // Show game layout when session is active
  useEffect(() => {
    if (currentSession) {
      setShowLobby(false);
    }
  }, [currentSession]);

  const handleBackToLobby = async () => {
    // If in a session, perform leave before going to lobby
    if (currentSession && connected && userId) {
      try {
        if (currentSession.hostUserId === userId) {
          // Host: end the session (broadcasts session_ended to players)
          await fetch(`http://localhost:8000/api/sessions/${currentSession.id}/end?user_id=${userId}`, { method: 'POST' });
        } else {
          // Participant: leave only
          await fetch(`http://localhost:8000/api/sessions/${currentSession.id}/leave?user_id=${userId}`, { method: 'POST' });
          leaveSessionSock(currentSession.id, userId);
        }
      } catch (e) {
        console.warn('Failed to call session leave/end API:', e);
      }
      clearChat();
      clearNotifications();
      setSession(null);
    }
    setShowLobby(true);
  };

  const handleBackToCharacterSelect = () => {
    // Clear character selection and go back to character management
    setSelectedCharacter(null);
    setCharacter(null);
  };

  const handleSelectCharacter = (character: Character) => {
    setSelectedCharacter(character);
    setCharacter({
      id: character.id,
      name: character.name,
      data: character.data,
    });
  };

  // Show login if not authenticated
  if (!isAuthenticated) {
    return <LoginForm />;
  }

  // Show character management if no character selected
  if (!selectedCharacter) {
    return <CharacterManagement onSelectCharacter={handleSelectCharacter} />;
  }

  return (
    <div className="h-screen w-screen bg-slate-50 text-slate-700 font-sans selection:bg-primary-100 selection:text-primary-900 overflow-hidden flex flex-col">
      
      {/* Navbar / Header Area - Application Shell */}
      <header className="flex-none relative w-full h-16 bg-white border-b border-slate-200 z-50 shadow-sm">
        <div className="h-full w-[95%] max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Back Button - Session View: back to lobby, Lobby View: back to character select */}
            {!showLobby ? (
              <button
                onClick={handleBackToLobby}
                className="group flex items-center justify-center w-8 h-8 rounded-full hover:bg-slate-100 text-slate-500 hover:text-blue-600 transition-all border border-transparent hover:border-slate-200"
                title="로비로 돌아가기"
              >
                <span className="text-lg group-hover:-translate-x-0.5 transition-transform">←</span>
              </button>
            ) : (
              <button
                onClick={handleBackToCharacterSelect}
                className="group flex items-center justify-center w-8 h-8 rounded-full hover:bg-slate-100 text-slate-500 hover:text-blue-600 transition-all border border-transparent hover:border-slate-200"
                title="캐릭터 선택으로 돌아가기"
              >
                <span className="text-lg group-hover:-translate-x-0.5 transition-transform">←</span>
              </button>
            )}

            {/* Logo / Title area */}
            <div className="flex items-center gap-2">
              <h1 className="text-lg sm:text-xl font-bold text-slate-800 tracking-tight whitespace-nowrap">
                TRPG World 
                <span className="text-slate-400 font-normal text-sm ml-2 hidden md:inline-block border-l border-slate-300 pl-2">
                  Digital Tabletop
                </span>
              </h1>
            </div>
          </div>

          {/* Connection Status Pill */}
          <div className={`px-4 py-2 rounded-lg flex items-center gap-2.5 text-sm font-semibold transition-all whitespace-nowrap shadow-sm border ${
            connected 
              ? 'bg-green-50 text-green-700 border-green-200' 
              : error 
              ? 'bg-red-50 text-red-700 border-red-200' 
              : 'bg-yellow-50 text-yellow-700 border-yellow-200'
          }`}>
            <div className={`w-2.5 h-2.5 rounded-full ${
              connected ? 'bg-green-500' : error ? 'bg-red-500' : 'bg-yellow-500'
            } ${connected ? 'animate-pulse' : ''}`} />
            <span className="hidden sm:inline">
              {connected ? '시스템 온라인' : error ? '연결 오류' : '연결 중...'}
            </span>
            {/* Mobile-only concise status */}
            <span className="inline sm:hidden uppercase text-xs font-bold">
              {connected ? '온라인' : error ? '오류' : '...'}
            </span>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 relative w-full overflow-hidden bg-slate-50">
        {error && (
          <div className="absolute top-6 left-1/2 -translate-x-1/2 w-[95%] max-w-7xl px-4 py-2 bg-red-50 text-red-700 border border-red-200 rounded-lg text-sm shadow-sm flex items-start gap-3 animate-fade-in-down z-40">
             <span className="text-lg">⚠️</span>
             <div className="flex-1">
               <p className="font-semibold">연결 오류</p>
               <p>{error}</p>
             </div>
          </div>
        )}
        
        {/* Show lobby or game based on state */}
        {showLobby ? (
          <div className="h-full w-full overflow-y-auto py-6">
            <div className="flex flex-col items-center justify-center w-[95%] max-w-7xl mx-auto min-h-full">
              <div className="w-full text-center mb-8 sm:mb-12">
                <h2 className="text-3xl sm:text-4xl font-extrabold text-slate-900 mb-4 tracking-tight">
                  어서 오세요, {selectedCharacter?.name}님
                </h2>
                <p className="text-base sm:text-lg text-slate-500 max-w-2xl mx-auto px-4">
                  당신을 위한 모험이 기다리고 있습니다!
                </p>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 sm:gap-8 w-full max-w-6xl cursor-default pb-12">
                {/* Session Creation */}
                <div className="h-full">
                  <SessionCreationForm />
                </div>
                
                {/* Session List */}
                <div className="h-full">
                  <SessionList />
                </div>

                {/* Host Sessions Manager */}
                <div className="h-full">
                  <HostSessionsManager />
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="h-full w-full flex items-center justify-center p-6">
            <div className="w-[95%] max-w-7xl h-full border border-slate-200 bg-white rounded-xl shadow-sm overflow-hidden">
              <GameLayout />
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
