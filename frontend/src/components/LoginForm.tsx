import { useState } from 'react';
import { useAuthStore } from '../stores/authStore';
import { login as apiLogin, register as apiRegister } from '../services/api';

export default function LoginForm() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [accessCode, setAccessCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [isRegisterMode, setIsRegisterMode] = useState(false);
  
  const login = useAuthStore((state) => state.login);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isRegisterMode) {
        // Register mode
        const data = await apiRegister({ username, password, access_code: accessCode });
        login(data.user_id, data.username);
      } else {
        // Login mode
        const data = await apiLogin({ username, password });
        login(data.user_id, data.username);
      }
    } catch (err: any) {
      setError(err.message || (isRegisterMode ? 'Registration failed' : 'Login failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="bg-white p-8 rounded-xl shadow-card w-full max-w-md border border-slate-200">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-slate-800 mb-2">TRPG World</h1>
          <p className="text-slate-500 text-sm">
            {isRegisterMode ? '새 계정을 만들어 모험을 시작하세요' : '로그인하여 모험을 시작하세요'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="username" className="block text-sm font-medium text-slate-700 mb-2">
              사용자 이름
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              placeholder="사용자 이름을 입력하세요"
              required
              disabled={loading}
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-2">
              비밀번호
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              placeholder="비밀번호를 입력하세요"
              required
              disabled={loading}
            />
          </div>

          {isRegisterMode && (
            <div>
              <label htmlFor="accessCode" className="block text-sm font-medium text-slate-700 mb-2">
                인증 코드
              </label>
              <input
                id="accessCode"
                type="text"
                value={accessCode}
                onChange={(e) => setAccessCode(e.target.value)}
                className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                placeholder="인증 코드를 입력하세요"
                required
                disabled={loading}
              />
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
          >
            {loading 
              ? (isRegisterMode ? '회원가입 중...' : '로그인 중...') 
              : (isRegisterMode ? '회원가입' : '로그인')
            }
          </button>
        </form>

        <div className="mt-6 text-center">
          <button
            type="button"
            onClick={() => {
              setIsRegisterMode(!isRegisterMode);
              setError('');
              setAccessCode('');
            }}
            className="text-blue-600 hover:text-blue-700 text-sm font-medium transition-colors"
          >
            {isRegisterMode ? '이미 계정이 있으신가요? 로그인' : '계정이 없으신가요? 회원가입'}
          </button>
        </div>

        {!isRegisterMode && (
          <div className="mt-6 text-center text-sm text-slate-500 bg-slate-50 rounded-lg p-4 border border-slate-200">
            <p className="font-semibold text-slate-700 mb-2">테스트 계정:</p>
            <p className="mt-1">user1 / 1234</p>
            <p>user2 / 1234</p>
          </div>
        )}
      </div>
    </div>
  );
}
