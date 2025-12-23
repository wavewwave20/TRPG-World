import { useState } from 'react';
import { createCharacter, getCharacter, ApiError } from '../services/api';
import { useGameStore } from '../stores/gameStore';
import CharacterStatsPanel from './CharacterStatsPanel';

export default function LeftPane() {
  const [characterName, setCharacterName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loadingParticipant, setLoadingParticipant] = useState(false);
  
  const currentSession = useGameStore((state) => state.currentSession);
  const currentCharacter = useGameStore((state) => state.currentCharacter);
  const participants = useGameStore((state) => state.participants);
  const selectedParticipant = useGameStore((state) => state.selectedParticipant);
  const setCharacter = useGameStore((state) => state.setCharacter);
  const setSelectedParticipant = useGameStore((state) => state.setSelectedParticipant);
  
  // Display character: selected participant's character or current character
  const displayCharacter = selectedParticipant?.character || currentCharacter;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Clear previous messages
    setError(null);
    setSuccess(null);
    
    // Validate inputs
    if (!characterName.trim()) {
      setError('Character name is required');
      return;
    }
    
    if (!currentSession) {
      setError('Please create or join a session first');
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      // For now, use a hardcoded user ID (will be replaced with auth in later phases)
      const userId = 1;
      
      // Create character via API (Requirements 6.1, 6.2, 6.3, 6.4)
      const response = await createCharacter({
        session_id: currentSession.id,
        user_id: userId,
        name: characterName.trim()
      });
      
      // Update game store with created character
      setCharacter({
        id: response.id,
        name: response.name,
        data: response.data
      });
      
      // Display success message
      setSuccess(`Character "${response.name}" created successfully!`);
      
      // Clear form
      setCharacterName('');
    } catch (err) {
      // Display error message
      if (err instanceof ApiError) {
        setError(`Failed to create character: ${err.message}`);
      } else if (err instanceof Error) {
        setError(`Failed to create character: ${err.message}`);
      } else {
        setError('Failed to create character: Unknown error');
      }
    } finally {
      setIsSubmitting(false);
    }
  };
  
  const handleParticipantClick = async (participant: typeof participants[0]) => {
    // If clicking the same participant, deselect
    if (selectedParticipant?.user_id === participant.user_id) {
      setSelectedParticipant(null);
      return;
    }
    
    // If character data is already loaded, just select
    if (participant.character) {
      setSelectedParticipant(participant);
      return;
    }
    
    // Load character data from backend
    setLoadingParticipant(true);
    try {
      const characterData = await getCharacter(participant.character_id);
      
      // Update participant with character data
      const updatedParticipant = {
        ...participant,
        character: {
          id: characterData.id,
          name: characterData.name,
          data: characterData.data
        }
      };
      
      // Update participants list in store
      const updatedParticipants = participants.map(p => 
        p.user_id === participant.user_id ? updatedParticipant : p
      );
      useGameStore.getState().setParticipants(updatedParticipants);
      
      // Select the updated participant
      setSelectedParticipant(updatedParticipant);
    } catch (err) {
      console.error('Failed to load participant character:', err);
      setError('캐릭터 정보를 불러올 수 없습니다.');
    } finally {
      setLoadingParticipant(false);
    }
  };

  return (
    <div className="h-full flex flex-col overflow-y-auto custom-scrollbar bg-slate-50/30">
      <div className="p-4 border-b border-slate-200 bg-white sticky top-0 z-10">
        <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
          <span className="text-blue-500">◈</span> 캐릭터
        </h2>
      </div>
      
      {/* Removed judgment status banner per request */}
      
      <div className="p-4 flex-1">
        {/* Character Creation Form - Show only if no character exists */}
        {!currentCharacter && (
          <div className="mb-6 bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
            <h3 className="text-xs font-bold uppercase tracking-wider mb-4 text-slate-500">정체성 생성</h3>
            
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="character-name" className="block text-xs font-bold text-slate-700 mb-1">
                  이름
                </label>
                <input
                  id="character-name"
                  type="text"
                  value={characterName}
                  onChange={(e) => setCharacterName(e.target.value)}
                  placeholder="예: 엘라라 문위스퍼"
                  className="w-full bg-slate-50 text-slate-900 px-3 py-2 rounded border border-slate-200 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-slate-400"
                  disabled={isSubmitting || !currentSession}
                  maxLength={100}
                />
              </div>
              
              {/* Error Message */}
              {error && (
                <div className="bg-red-50 text-red-700 px-3 py-2 rounded text-xs border border-red-200">
                  {error}
                </div>
              )}
              
              {/* Success Message */}
              {success && (
                <div className="bg-green-50 text-green-700 px-3 py-2 rounded text-xs border border-green-200">
                  {success}
                </div>
              )}
              
              <button
                type="submit"
                disabled={isSubmitting || !currentSession}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white px-3 py-2 rounded-lg text-sm font-semibold transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting ? '생성 중...' : '페르소나 생성'}
              </button>
              
              {!currentSession && (
                <p className="text-xs text-yellow-600 text-center italic mt-2 bg-yellow-50 p-1 rounded">
                  * 먼저 세션에 참가하세요
                </p>
              )}
            </form>
          </div>
        )}
        
        {/* Character Display - Show when character exists */}
        {displayCharacter && (
          <>
            {/* Show indicator if viewing another participant's character */}
            {selectedParticipant && (
              <div className="mb-3 bg-blue-50 border border-blue-200 rounded-lg p-2 flex items-center justify-between">
                <span className="text-xs text-blue-700 font-medium">
                  {selectedParticipant.character_name}의 정보
                </span>
                <button
                  onClick={() => setSelectedParticipant(null)}
                  className="text-blue-600 hover:text-blue-800 text-xs font-semibold"
                >
                  내 캐릭터 보기
                </button>
              </div>
            )}
            
            {/* Character Stats Panel - D20 ability scores, skills, weaknesses */}
            <div className="mb-6">
              <CharacterStatsPanel character={displayCharacter} />
            </div>
            
            {/* Inventory Section */}
            <div className="mb-6">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 flex items-center gap-2">
                인벤토리
              </h3>
              <div className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
                {displayCharacter.data.inventory && displayCharacter.data.inventory.length > 0 ? (
                  <ul className="divide-y divide-slate-100">
                    {displayCharacter.data.inventory?.map((item, index) => (
                      <li key={index} className="text-slate-700 px-4 py-3 hover:bg-slate-50 flex items-center gap-2 transition-colors text-sm">
                        <span className="text-blue-400 text-xs">●</span> {item}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="text-sm text-slate-400 italic p-6 text-center bg-slate-50">
                    비었음
                  </div>
                )}
              </div>
            </div>
          </>
        )}
        
        {/* World Info Section */}
        <div className="mt-8 pt-6 border-t border-slate-200">
          <h3 className="text-xs font-bold text-slate-400 uppercase mb-3">현재 세계</h3>
          {currentSession ? (
            <div className="text-xs space-y-2 bg-slate-50 p-3 rounded-lg border border-slate-200">
              <div className="flex justify-between items-center">
                <span className="text-slate-500 font-medium">세션 이름</span>
                <span className="text-slate-900 font-semibold text-right truncate max-w-[120px]">{currentSession.title}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500 font-medium">세계 ID</span>
                <span className="text-slate-700 font-mono bg-white px-1.5 py-0.5 rounded border border-slate-200">{currentSession.id}</span>
              </div>
            </div>
          ) : (
            <div className="text-xs text-slate-500 italic text-center p-2">
              현재 세계에 없습니다
            </div>
          )}
          
          {/* Participants List */}
          {currentSession && participants.length > 0 && (
            <div className="mt-4">
              <h4 className="text-xs font-bold text-slate-400 uppercase mb-2">참가자 ({participants.length})</h4>
              <div className="space-y-1">
                {participants.map((participant) => (
                  <button
                    key={participant.user_id}
                    onClick={() => handleParticipantClick(participant)}
                    disabled={loadingParticipant}
                    className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors ${
                      selectedParticipant?.user_id === participant.user_id
                        ? 'bg-blue-100 text-blue-800 font-semibold border border-blue-300'
                        : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
                    } ${loadingParticipant ? 'opacity-50 cursor-wait' : 'cursor-pointer'}`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-green-500">●</span>
                      <span className="truncate">{participant.character_name}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
