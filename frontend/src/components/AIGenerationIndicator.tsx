import { useEffect, useState } from 'react';

interface AIGenerationIndicatorProps {
  isGenerating: boolean;
}

export default function AIGenerationIndicator({ isGenerating }: AIGenerationIndicatorProps) {
  const [shouldRender, setShouldRender] = useState(false);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (isGenerating) {
      // Start rendering immediately
      setShouldRender(true);
      // Trigger fade-in after a brief delay to allow CSS transition
      setTimeout(() => setIsVisible(true), 10);
    } else {
      // Trigger fade-out
      setIsVisible(false);
      // Remove from DOM after transition completes
      const timeout = setTimeout(() => setShouldRender(false), 300);
      return () => clearTimeout(timeout);
    }
  }, [isGenerating]);

  if (!shouldRender) {
    return null;
  }

  return (
    <div
      className={`absolute inset-0 z-30 flex items-center justify-center bg-slate-900/20 backdrop-blur-sm transition-opacity duration-300 ${
        isVisible ? 'opacity-100' : 'opacity-0'
      }`}
      role="alert"
      aria-live="assertive"
      aria-busy="true"
      aria-label="AI가 스토리를 생성하고 있습니다"
    >
      <div className="bg-white rounded-2xl shadow-2xl px-8 py-6 flex flex-col items-center gap-4 border border-slate-200 max-w-sm mx-4">
        {/* Animated Spinner */}
        <div className="relative w-16 h-16" aria-hidden="true">
          {/* Outer rotating ring */}
          <div className="absolute inset-0 border-4 border-slate-200 rounded-full"></div>
          <div className="absolute inset-0 border-4 border-transparent border-t-blue-600 rounded-full animate-spin"></div>
          
          {/* Inner pulsing circle */}
          <div className="absolute inset-3 bg-blue-100 rounded-full animate-pulse"></div>
          
          {/* Center icon */}
          <div className="absolute inset-0 flex items-center justify-center text-2xl">
            ✨
          </div>
        </div>
        
        {/* Loading Text */}
        <div className="text-center">
          <p className="text-slate-800 font-semibold text-base mb-1" id="ai-loading-message">
            AI가 스토리를 생성하고 있습니다...
          </p>
          <p className="text-slate-500 text-xs" aria-describedby="ai-loading-message">
            잠시만 기다려주세요
          </p>
        </div>
        
        {/* Animated dots */}
        <div className="flex gap-1.5" aria-hidden="true">
          <span className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
          <span className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
          <span className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
        </div>
      </div>
    </div>
  );
}
