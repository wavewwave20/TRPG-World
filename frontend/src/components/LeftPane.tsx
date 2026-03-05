import { useState } from 'react';
import { createCharacter, ApiError } from '../services/api';
import { useGameStore } from '../stores/gameStore';
import CharacterStatsPanel from './CharacterStatsPanel';

export default function LeftPane() {
  const [characterName, setCharacterName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const currentSession = useGameStore((state) => state.currentSession);
  const currentCharacter = useGameStore((state) => state.currentCharacter);
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
  
  return (
    <div className="h-full flex flex-col overflow-y-auto custom-scrollbar bg-slate-50/30">
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
                  className="w-full bg-slate-50 text-slate-900 px-3 py-2.5 rounded border border-slate-200 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-slate-400"
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
                className="w-full bg-blue-600 hover:bg-blue-700 text-white px-3 py-2.5 rounded-lg text-sm font-semibold transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
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
                  className="text-blue-600 hover:text-blue-800 text-xs font-semibold py-2 min-h-[44px] flex items-center"
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
                    {displayCharacter.data.inventory?.map((item, index) => {
                      if (typeof item === 'string') {
                        return (
                          <li
                            key={index}
                            className="text-slate-700 px-4 py-3 hover:bg-slate-50 flex items-center gap-2 transition-colors text-sm"
                          >
                            <span className="text-blue-400 text-xs">●</span>
                            {item}
                          </li>
                        );
                      }

                      const quantity = item.quantity && item.quantity > 1 ? ` x${item.quantity}` : '';
                      const typeLabel = item.type === 'consumable' ? '소모품' : '장비';
                      return (
                        <li
                          key={index}
                          className="text-slate-700 px-4 py-3 hover:bg-slate-50 flex items-start gap-2 transition-colors text-sm"
                        >
                          <span className="text-blue-400 text-xs mt-1">●</span>
                          <div className="min-w-0">
                            <div>
                              {item.name} [{typeLabel}]{quantity}
                            </div>
                            {item.description && (
                              <div className="text-xs text-slate-500 mt-0.5">{item.description}</div>
                            )}
                          </div>
                        </li>
                      );
                    })}
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
        
      </div>
    </div>
  );
}
