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
import SessionInfoDropdown from './components/SessionInfoDropdown';
import LLMSettingsPage from './components/LLMSettingsPage';
import type { Character as BaseCharacter } from './types/character';
import './App.css'

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

interface Character extends BaseCharacter {
  user_id: number;
  created_at: string;
}

function App() {
  const connect = useSocketStore((state) => state.connect);
  const disconnect = useSocketStore((state) => state.disconnect);
  const reconnect = useSocketStore((state) => state.reconnect);
  const connected = useSocketStore((state) => state.connected);
  const error = useSocketStore((state) => state.error);
  const currentSession = useGameStore((state) => state.currentSession);
  const setCharacter = useGameStore((state) => state.setCharacter);
  const setSession = useGameStore((state) => state.setSession);
  const clearNotifications = useGameStore((state) => state.clearNotifications);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const userId = useAuthStore((state) => state.userId);
  const leaveSessionSock = useSocketStore((state) => state.leaveSession);
  const clearChat = useChatStore((state) => state.clear);
  
  const isAdmin = useAuthStore((state) => state.isAdmin);
  const checkAdmin = useAuthStore((state) => state.checkAdmin);

  const [selectedCharacter, setSelectedCharacter] = useState<Character | null>(null);
  const [showLLMSettings, setShowLLMSettings] = useState(false);
  const [showMobileHeaderMenu, setShowMobileHeaderMenu] = useState(false);
  const showLobby = !currentSession;

  useEffect(() => {
    // Initialize socket connection on mount if authenticated
    if (isAuthenticated) {
      connect();
      checkAdmin();
    }

    // Cleanup: disconnect on unmount
    return () => {
      disconnect();
    };
  }, [connect, disconnect, isAuthenticated, checkAdmin]);

  const handleBackToLobby = async () => {
    // If in a session, always try to leave gracefully before returning to lobby.
    // Host can explicitly end the room via the dedicated "방 종료" button.
    if (currentSession && userId) {
      try {
        await fetch(`${API_BASE_URL}/api/sessions/${currentSession.id}/leave?user_id=${userId}`, {
          method: 'POST'
        });
        if (connected) {
          leaveSessionSock(currentSession.id, userId);
        }
      } catch (e) {
        console.warn('Failed to call session leave/end API:', e);
      }
      clearChat();
      clearNotifications();
      setSession(null);
    }
  };

  const handleBackToCharacterSelect = () => {
    // Clear character selection and go back to character management
    setSelectedCharacter(null);
    setCharacter(null);
  };

  const handleEndSession = async () => {
    if (!currentSession || !userId) return;
    if (!confirm('정말로 세션을 종료하시겠습니까? 모든 참가자가 나가게 됩니다.')) return;
    try {
      await fetch(`${API_BASE_URL}/api/sessions/${currentSession.id}/end?user_id=${userId}`, { method: 'POST' });
    } catch (e) {
      console.warn('Failed to end session:', e);
    }
    clearChat();
    clearNotifications();
    setSession(null);
  };

  const isHost = currentSession?.hostUserId === userId;

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
      <header className="flex-none relative w-full h-14 sm:h-16 bg-white border-b border-slate-200 z-50 shadow-sm">
        <div className="h-full w-[96%] max-w-7xl mx-auto flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            {/* Back Button - Session View: back to lobby, Lobby View: back to character select */}
            {!showLobby ? (
              <button
                onClick={handleBackToLobby}
                className="group flex items-center justify-center w-10 h-10 lg:w-8 lg:h-8 rounded-full hover:bg-slate-100 text-slate-500 hover:text-blue-600 transition-all border border-transparent hover:border-slate-200"
                title="로비로 돌아가기"
              >
                <span className="text-lg group-hover:-translate-x-0.5 transition-transform">←</span>
              </button>
            ) : (
              <button
                onClick={handleBackToCharacterSelect}
                className="group flex items-center justify-center w-10 h-10 lg:w-8 lg:h-8 rounded-full hover:bg-slate-100 text-slate-500 hover:text-blue-600 transition-all border border-transparent hover:border-slate-200"
                title="캐릭터 선택으로 돌아가기"
              >
                <span className="text-lg group-hover:-translate-x-0.5 transition-transform">←</span>
              </button>
            )}

            {/* Logo / Title area */}
            <div className="flex items-center gap-2">
              <h1 className="text-base sm:text-xl font-bold text-slate-800 tracking-tight whitespace-nowrap">
                TRPG World 
                <span className="text-slate-400 font-normal text-sm ml-2 hidden md:inline-block border-l border-slate-300 pl-2">
                  Digital Tabletop
                </span>
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-1 sm:gap-2 min-w-0 relative">
            {!showLobby && currentSession && <SessionInfoDropdown />}

            {/* mobile compact menu */}
            {!showLobby && (
              <div className="sm:hidden relative">
                <button
                  onClick={() => setShowMobileHeaderMenu((v) => !v)}
                  className="w-9 h-9 rounded-lg border border-slate-200 bg-white text-slate-700"
                >
                  ☰
                </button>
                {showMobileHeaderMenu && (
                  <div className="absolute right-0 top-full mt-2 w-44 rounded-lg border border-slate-200 bg-white shadow-lg p-2 z-50">
                    {isHost && !showLobby && (
                      <>
                        <button
                          onClick={() => {
                            window.dispatchEvent(new Event('oc:open_moderation_modal'));
                            setShowMobileHeaderMenu(false);
                          }}
                          className="w-full text-left px-2 py-2 text-xs rounded hover:bg-slate-50"
                        >
                          행동 결정
                        </button>
                        <button
                          onClick={() => {
                            window.dispatchEvent(new Event('oc:open_story_steering_modal'));
                            setShowMobileHeaderMenu(false);
                          }}
                          className="w-full text-left px-2 py-2 text-xs rounded hover:bg-slate-50"
                        >
                          스토리 조정
                        </button>
                        <button
                          onClick={() => {
                            window.dispatchEvent(new Event('oc:host_advance_story'));
                            setShowMobileHeaderMenu(false);
                          }}
                          className="w-full text-left px-2 py-2 text-xs rounded hover:bg-slate-50"
                        >
                          스토리 진행
                        </button>
                        <hr className="my-1 border-slate-200" />
                      </>
                    )}
                    {isHost && (
                      <button onClick={() => { handleEndSession(); setShowMobileHeaderMenu(false); }} className="w-full text-left px-2 py-2 text-xs rounded hover:bg-slate-50 text-red-600">
                        방 종료
                      </button>
                    )}
                    <div className="px-2 py-2 text-xs text-slate-600">
                      상태: {connected ? '온라인' : error ? '오류' : '연결중'}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* desktop controls */}
            {!showLobby && isHost && (
              <button
                onClick={handleEndSession}
                className="hidden sm:inline-flex px-2 sm:px-3 py-1.5 sm:py-2 rounded-lg text-[11px] sm:text-sm font-semibold bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 transition-all whitespace-nowrap"
              >
                방 종료
              </button>
            )}

            {/* Admin LLM Settings Button */}
            {isAdmin && showLobby && (
              <button
                onClick={() => setShowLLMSettings(true)}
                className="flex items-center justify-center w-10 h-10 lg:w-8 lg:h-8 rounded-full hover:bg-slate-100 text-slate-500 hover:text-blue-600 transition-all border border-transparent hover:border-slate-200"
                title="LLM Settings"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" />
                </svg>
              </button>
            )}

            <div className={`hidden sm:flex px-2 sm:px-4 py-1.5 sm:py-2 rounded-lg items-center gap-1.5 sm:gap-2 text-xs sm:text-sm font-semibold transition-all whitespace-nowrap shadow-sm border shrink-0 ${
              connected
                ? 'bg-green-50 text-green-700 border-green-200'
                : error
                ? 'bg-red-50 text-red-700 border-red-200'
                : 'bg-yellow-50 text-yellow-700 border-yellow-200'
            }`}>
              <div className={`w-2.5 h-2.5 rounded-full ${
                connected ? 'bg-green-500' : error ? 'bg-red-500' : 'bg-yellow-500'
              } ${connected ? 'animate-pulse' : ''}`} />
              <span>
                {connected ? '시스템 온라인' : error ? '연결 오류' : '연결 중...'}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 relative w-full overflow-hidden bg-slate-50">
        {/* Disconnection Banner with Reconnect Button */}
        {!connected && isAuthenticated && (
          <div className="absolute top-0 left-0 right-0 px-4 py-2.5 bg-yellow-50 text-yellow-800 border-b border-yellow-200 text-sm flex items-center justify-center gap-3 z-40">
            <div className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse" />
            <span className="font-medium">서버와 연결이 끊어졌습니다. 재연결 중...</span>
            <button
              onClick={reconnect}
              className="px-3 py-1.5 bg-yellow-600 hover:bg-yellow-700 text-white text-xs font-bold rounded-lg transition-colors"
            >
              재접속
            </button>
          </div>
        )}
        
        {/* Show LLM Settings, lobby, or game based on state */}
        {showLLMSettings ? (
          <div className="h-full w-full overflow-y-auto py-6">
            <LLMSettingsPage onBack={() => setShowLLMSettings(false)} />
          </div>
        ) : showLobby ? (
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
          <div className="h-full w-full flex items-center justify-center p-0 lg:p-6">
            <div className="w-full lg:w-[95%] lg:max-w-7xl h-full lg:border lg:border-slate-200 bg-white lg:rounded-xl lg:shadow-sm overflow-hidden">
              <GameLayout />
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
