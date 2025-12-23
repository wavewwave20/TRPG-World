import { useState, memo } from 'react';
import type { JudgmentSummary } from '../services/api';

interface JudgmentResultsButtonProps {
  judgments: JudgmentSummary[];
  onOpenModal?: () => void;
  isComplete?: boolean;
}

function JudgmentResultsButton({ judgments, onOpenModal }: JudgmentResultsButtonProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!judgments || judgments.length === 0) {
    return null;
  }

  // Check if all judgments are complete (all have dice results and outcomes)
  const allComplete = judgments.every((j) => j.dice_result !== null && j.outcome !== null);
  const buttonText = allComplete ? '판정 결과 보기' : '판정 진행 중';
  const buttonColor = allComplete ? 'text-blue-600 hover:text-blue-700' : 'text-amber-600 hover:text-amber-700';
  const buttonIcon = allComplete ? '🎲' : '⏳';

  const getOutcomeColor = (outcome: string | null) => {
    switch (outcome) {
      case 'critical_success':
        return 'text-green-700 bg-green-100';
      case 'success':
        return 'text-green-600 bg-green-50';
      case 'failure':
        return 'text-red-600 bg-red-50';
      case 'critical_failure':
        return 'text-red-700 bg-red-100';
      default:
        return 'text-slate-600 bg-slate-50';
    }
  };

  const getOutcomeText = (outcome: string | null) => {
    switch (outcome) {
      case 'critical_success':
        return '대성공';
      case 'success':
        return '성공';
      case 'failure':
        return '실패';
      case 'critical_failure':
        return '대실패';
      default:
        return '진행 중';
    }
  };

  const getOutcomeIcon = (outcome: string | null) => {
    switch (outcome) {
      case 'critical_success':
        return '🌟';
      case 'success':
        return '✅';
      case 'failure':
        return '❌';
      case 'critical_failure':
        return '💥';
      default:
        return '⏳';
    }
  };

  return (
    <div className="mt-3 border-t border-slate-200 pt-3">
      <div className="flex items-center gap-2">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className={`flex-1 flex items-center gap-2 text-sm ${buttonColor} font-medium transition-colors`}
        >
          <span>{buttonIcon}</span>
          <span>{buttonText} ({judgments.length})</span>
          <svg
            className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {onOpenModal && (
          <button
            onClick={onOpenModal}
            className="px-3 py-1 text-xs bg-blue-100 hover:bg-blue-200 text-blue-700 rounded-md font-medium transition-colors"
            title="판정 모달 다시 열기"
          >
            모달 열기
          </button>
        )}
      </div>

      {isExpanded && (
        <div className="mt-3 space-y-2">
          {judgments.map((judgment) => (
            <div key={judgment.id} className={`p-3 rounded-lg border ${getOutcomeColor(judgment.outcome)}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-gradient-to-br from-slate-400 to-slate-600 flex items-center justify-center text-white text-xs font-bold">
                    {judgment.character_name.charAt(0).toUpperCase()}
                  </div>
                  <span className="font-semibold text-sm">{judgment.character_name}</span>
                </div>
                <span className="text-sm font-bold flex items-center gap-1">
                  {getOutcomeIcon(judgment.outcome)}
                  {getOutcomeText(judgment.outcome)}
                </span>
              </div>

              <p className="text-xs text-slate-600 mb-2 line-clamp-2">{judgment.action_text}</p>

              {judgment.dice_result !== null && (
                <div className="flex items-center gap-3 text-xs">
                  <span className="flex items-center gap-1">
                    🎲 <strong>{judgment.dice_result}</strong>
                  </span>
                  <span className="text-slate-500">{judgment.modifier >= 0 ? '+' : ''}{judgment.modifier}</span>
                  <span className="text-slate-500">=</span>
                  <span className="font-bold text-blue-600">{judgment.final_value}</span>
                  <span className="text-slate-400">vs</span>
                  <span className="font-medium">DC {judgment.difficulty}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default memo(JudgmentResultsButton);

