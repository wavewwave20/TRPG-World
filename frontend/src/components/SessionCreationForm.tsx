import { useState } from 'react';
import { createSession, ApiError } from '../services/api';
import { useGameStore } from '../stores/gameStore';
import { useSocketStore } from '../stores/socketStore';
import { useAuthStore } from '../stores/authStore';
import { useChatStore } from '../stores/chatStore';

interface SessionCreationFormProps {
  onSuccess?: () => void;
}

export default function SessionCreationForm({ onSuccess }: SessionCreationFormProps) {
  const [title, setTitle] = useState('');
  const [worldPrompt, setWorldPrompt] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  const setSession = useGameStore((state) => state.setSession);
  const clearNotifications = useGameStore((state) => state.clearNotifications);
  const currentCharacter = useGameStore((state) => state.currentCharacter);
  const joinSession = useSocketStore((state) => state.joinSession);
  const connected = useSocketStore((state) => state.connected);
  const userId = useAuthStore((state) => state.userId);
  const clearChat = useChatStore((state) => state.clear);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Clear previous messages
    setError(null);
    setSuccess(null);
    
    // Validate inputs
    if (!title.trim()) {
      setError('Title is required');
      return;
    }
    
    if (!worldPrompt.trim()) {
      setError('World prompt is required');
      return;
    }

    if (!userId) {
      setError('User not authenticated');
      return;
    }

    if (!currentCharacter) {
      setError('Select a character before creating a session');
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      // Clear chat and system logs before joining new session
      clearChat();
      clearNotifications();
      
      // Create session via API (Requirements 4.1, 4.2, 4.3)
      const response = await createSession({
        host_user_id: userId,
        title: title.trim(),
        world_prompt: worldPrompt.trim()
      });
      
      // Update game store with created session
      setSession({
        id: response.session_id,
        title: title.trim(),
        hostUserId: userId
      });
      
      // Ensure DB participant record exists so list shows correct count
      try {
        await fetch(`http://localhost:8000/api/sessions/${response.session_id}/join`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: userId,
            character_id: currentCharacter.id,
          }),
        });
      } catch (e) {
        console.warn('Failed to register as participant on create:', e);
      }

      // Emit join_session socket event (Requirements 5.1, 5.2)
      if (connected) {
        joinSession(response.session_id, userId, currentCharacter.id);
      }
      
      // Display success message
      setSuccess(`Session "${title}" created successfully! (ID: ${response.session_id})`);
      
      // Clear form
      setTitle('');
      setWorldPrompt('');
      
      // Call success callback if provided
      if (onSuccess) {
        onSuccess();
      }
    } catch (err) {
      // Display error message (Requirements 4.4)
      if (err instanceof ApiError) {
        setError(`Failed to create session: ${err.message}`);
      } else if (err instanceof Error) {
        setError(`Failed to create session: ${err.message}`);
      } else {
        setError('Failed to create session: Unknown error');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-card hover:shadow-card-hover transition-all duration-300 h-full flex flex-col">
      <div className="mb-6 pb-4 border-b border-slate-100">
        <h3 className="text-xl font-bold text-slate-800 flex items-center gap-2">
          <span className="text-2xl">✨</span> 새 세션
        </h3>
        <p className="text-slate-500 text-sm mt-1">
          플레이어들이 탐험할 새로운 세계를 만드세요.
        </p>
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-6 flex-1 flex flex-col">
        {/* Title Input */}
        <div className="space-y-1.5">
          <label htmlFor="session-title" className="block text-sm font-semibold text-slate-700">
            모험 제목 <span className="text-red-600">*</span>
          </label>
          <input
            id="session-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="예: 잃어버린 왕국의 전설"
            className="w-full bg-slate-50 border border-slate-200 text-slate-900 px-4 py-2.5 rounded-lg text-sm focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all placeholder:text-slate-400"
            disabled={isSubmitting}
            maxLength={255}
          />
        </div>
        
        {/* World Prompt Input */}
        <div className="space-y-1.5 flex-1">
          <label htmlFor="world-prompt" className="block text-sm font-semibold text-slate-700">
            세계관 설정 <span className="text-red-600">*</span>
          </label>
          <textarea
            id="world-prompt"
            value={worldPrompt}
            onChange={(e) => setWorldPrompt(e.target.value)}
            placeholder="세계의 장르, 분위기, 주요 규칙을 설명해주세요..."
            className="w-full h-32 bg-slate-50 border border-slate-200 text-slate-900 px-4 py-3 rounded-lg text-sm focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all resize-none placeholder:text-slate-400"
            disabled={isSubmitting}
          />
          <p className="text-xs text-slate-500 text-right">
            AI 게임 마스터가 이 정보를 바탕으로 이야기를 생성합니다.
          </p>
        </div>
        
        {/* Messages */}
        {error && (
          <div className="bg-red-50 border border-red-100 text-red-700 px-4 py-3 rounded-lg text-sm flex items-start gap-2">
            <span>⚠️</span> {error}
          </div>
        )}
        
        {success && (
          <div className="bg-green-50 border border-green-100 text-green-700 px-4 py-3 rounded-lg text-sm flex items-start gap-2">
            <span>✅</span> {success}
          </div>
        )}
        
        {/* Submit Button */}
        <div className="pt-2 mt-auto">
          <button
            type="submit"
            disabled={isSubmitting || !connected}
            className="w-full bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white px-6 py-3 rounded-lg text-base font-semibold shadow-sm transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none flex items-center justify-center gap-2"
          >
            {isSubmitting ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                생성 중...
              </span>
            ) : (
              '세션 생성'
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
