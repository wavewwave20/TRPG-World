import { useState, useRef, useEffect } from 'react';
import { useGameStore } from '../stores/gameStore';
import { useSocketStore } from '../stores/socketStore';
import { useChatStore } from '../stores/chatStore';
import { useAuthStore } from '../stores/authStore';

export default function RightPane() {
  const [text, setText] = useState('');
  const generalEndRef = useRef<HTMLDivElement>(null);
  const systemEndRef = useRef<HTMLDivElement>(null);

  const notifications = useGameStore((state) => state.notifications);
  const messages = useChatStore((state) => state.messages);
  const emit = useSocketStore((state) => state.emit);
  const connected = useSocketStore((state) => state.connected);
  const currentSession = useGameStore((state) => state.currentSession);
  const userId = useAuthStore((state) => state.userId);

  const canSend = connected && !!currentSession && !!userId && text.trim().length > 0;
  const canType = connected && !!currentSession && !!userId;
  const kstTime = new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit' });

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    generalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-scroll to bottom when new notifications arrive
  useEffect(() => {
    systemEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [notifications]);

  const handleSend = () => {
    if (!canSend || !currentSession || !userId) return;
    emit('chat_message', {
      session_id: currentSession.id,
      user_id: userId,
      message: text.trim(),
    });
    setText('');
  };

  // Filter general chat by current session
  const sessionMessages = currentSession ? messages.filter(m => m.session_id === currentSession.id) : messages;

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 bg-white">
        <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
          <span className="text-blue-500">💬</span> 채팅
        </h2>
      </div>

      {/* System Log Section (1/3) */}
      <div className="flex-none h-[33%] flex flex-col border-b border-slate-200">
        <div className="px-4 py-2 bg-slate-100 border-b border-slate-200">
          <h3 className="text-xs font-bold uppercase tracking-wide text-slate-600">시스템</h3>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-slate-50/50">
          {notifications.length === 0 ? (
            <div className="text-xs text-slate-400 italic text-center py-4">
              채널이 조용합니다...
            </div>
          ) : (
            <>
              {notifications.map((notification) => (
                <div
                  key={notification.id}
                  className={`rounded-lg p-2 border shadow-sm ${
                    (notification.type === 'alert' || notification.type === 'error') ? 'bg-red-50 border-red-400' : 'bg-white border-slate-200'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className={`text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${
                      notification.type === 'user_joined' ? 'bg-green-100 text-green-700' :
                      notification.type === 'user_left' ? 'bg-red-100 text-red-700' :
                      notification.type === 'action_submitted' ? 'bg-purple-100 text-purple-700' :
                      notification.type === 'story_committed' ? 'bg-blue-100 text-blue-700' :
                      (notification.type === 'alert' || notification.type === 'error') ? 'bg-red-600 text-white' :
                      'bg-slate-100 text-slate-700'
                    }`}>
                      {notification.type === 'user_joined' ? '입장' :
                       notification.type === 'user_left' ? '퇴장' :
                       notification.type === 'action_submitted' ? '행동' :
                       notification.type === 'story_committed' ? '이야기' :
                       notification.type === 'alert' ? '알림' :
                       notification.type === 'error' ? '오류' : '시스템'}
                    </div>
                    <div className="text-[10px] text-slate-400 font-mono">
                      {kstTime.format(notification.timestamp)}
                    </div>
                  </div>
                  <div 
                    className={`text-xs leading-snug ${
                      (notification.type === 'alert' || notification.type === 'error') ? 'font-bold' : ''
                    }`}
                    style={(notification.type === 'alert' || notification.type === 'error') ? { color: '#dc2626' } : { color: '#475569' }}
                  >
                    {notification.message}
                  </div>
                </div>
              ))}
              <div ref={systemEndRef} />
            </>
          )}
        </div>
      </div>

      {/* General Chat Section (2/3) */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="px-4 py-2 bg-slate-100 border-b border-slate-200">
          <h3 className="text-xs font-bold uppercase tracking-wide text-slate-600">일반 채팅</h3>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-slate-50/50 min-h-0">
          {sessionMessages.length === 0 ? (
            <div className="text-xs text-slate-400 italic text-center py-4">
              아직 메시지가 없습니다. 인사해보세요!
            </div>
          ) : (
            <>
              {sessionMessages.map((m, idx) => (
                <div key={idx} className="bg-white rounded-lg p-2 border border-slate-200 shadow-sm">
                  <div className="flex items-center justify-between mb-1">
                    <div className="text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded bg-slate-100 text-slate-700">
                      {m.character_name || m.username || 'Player'}
                    </div>
                    <div className="text-[10px] text-slate-400 font-mono">
                      {kstTime.format(m.timestamp)}
                    </div>
                  </div>
                  <div className="text-xs text-slate-700 leading-snug">
                    {m.message}
                  </div>
                </div>
              ))}
              <div ref={generalEndRef} />
            </>
          )}
        </div>

        {/* Input Section for General Chat */}
        <div className="p-3 border-t border-slate-200 bg-white">
          <div className="flex gap-2">
            <input
              type="text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && canSend) handleSend(); }}
              placeholder={currentSession ? '메시지 전송...' : '채팅하려면 세션에 참가하세요'}
              className={`flex-1 bg-slate-50 text-slate-900 px-3 py-2 rounded-lg text-xs border border-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all ${
                !canType ? 'opacity-60 cursor-not-allowed' : ''
              }`}
              disabled={!canType}
            />
            <button
              onClick={handleSend}
              className={`px-3 py-2 rounded-lg text-xs font-bold uppercase tracking-wide transition-all ${
                canSend ? 'bg-blue-600 hover:bg-blue-700 text-white' : 'bg-slate-200 text-slate-500 cursor-not-allowed opacity-60'
              }`}
              disabled={!canSend}
            >
              전송
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
