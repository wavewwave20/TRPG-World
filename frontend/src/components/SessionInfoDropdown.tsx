import { useState, useRef, useEffect } from 'react';
import { getCharacter } from '../services/api';
import { useGameStore } from '../stores/gameStore';

export default function SessionInfoDropdown() {
  const [isOpen, setIsOpen] = useState(false);
  const [loadingParticipant, setLoadingParticipant] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentSession = useGameStore((state) => state.currentSession);
  const participants = useGameStore((state) => state.participants);
  const selectedParticipant = useGameStore((state) => state.selectedParticipant);
  const setSelectedParticipant = useGameStore((state) => state.setSelectedParticipant);

  // Close on click outside
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const handleParticipantClick = async (participant: typeof participants[0]) => {
    if (selectedParticipant?.user_id === participant.user_id) {
      setSelectedParticipant(null);
      return;
    }

    if (participant.character) {
      setSelectedParticipant(participant);
      return;
    }

    setLoadingParticipant(true);
    try {
      const characterData = await getCharacter(participant.character_id);
      const updatedParticipant = {
        ...participant,
        character: {
          id: characterData.id,
          name: characterData.name,
          data: characterData.data,
        },
      };

      const updatedParticipants = participants.map((p) =>
        p.user_id === participant.user_id ? updatedParticipant : p
      );
      useGameStore.getState().setParticipants(updatedParticipants);
      setSelectedParticipant(updatedParticipant);
    } catch (err) {
      console.error('Failed to load participant character:', err);
    } finally {
      setLoadingParticipant(false);
    }
  };

  if (!currentSession) return null;

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Trigger */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm font-medium transition-all border ${
          isOpen
            ? 'bg-blue-50 text-blue-700 border-blue-200'
            : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
        }`}
      >
        <span className="truncate max-w-[80px] sm:max-w-[140px]">
          {currentSession.title}
        </span>
        <span className="flex items-center gap-0.5 text-xs text-slate-500 border-l border-slate-300 pl-1.5 ml-0.5">
          <span className="text-green-500">●</span>
          {participants.length}
        </span>
        <span className={`text-[10px] text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}>
          ▼
        </span>
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-64 bg-white rounded-xl shadow-lg border border-slate-200 overflow-hidden z-[100] animate-in fade-in slide-in-from-top-1 duration-150">
          {/* Session Info */}
          <div className="px-4 py-3 bg-slate-50 border-b border-slate-200">
            <div className="text-sm font-bold text-slate-800 truncate">
              {currentSession.title}
            </div>
            <div className="text-xs text-slate-500 mt-0.5">
              ID: <span className="font-mono bg-white px-1 py-0.5 rounded border border-slate-200">{currentSession.id}</span>
            </div>
          </div>

          {/* Participants */}
          <div className="px-3 py-2">
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">
              참가자 ({participants.length})
            </div>
            <div className="space-y-0.5 max-h-48 overflow-y-auto">
              {participants.map((participant) => (
                <button
                  key={participant.user_id}
                  onClick={() => handleParticipantClick(participant)}
                  disabled={loadingParticipant}
                  className={`w-full text-left px-2.5 py-2 rounded-lg text-xs transition-colors ${
                    selectedParticipant?.user_id === participant.user_id
                      ? 'bg-blue-50 text-blue-800 font-semibold border border-blue-200'
                      : 'text-slate-700 hover:bg-slate-50 border border-transparent'
                  } ${loadingParticipant ? 'opacity-50 cursor-wait' : 'cursor-pointer'}`}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-green-500 text-[8px]">●</span>
                    <span className="truncate">{participant.character_name}</span>
                  </div>
                </button>
              ))}
              {participants.length === 0 && (
                <div className="text-xs text-slate-400 italic text-center py-2">
                  참가자 없음
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
