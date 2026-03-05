import SessionCreationForm from './SessionCreationForm';

interface SessionCreationPageProps {
  onBack: () => void;
}

export default function SessionCreationPage({ onBack }: SessionCreationPageProps) {
  return (
    <div className="h-full w-full overflow-y-auto py-6">
      <div className="w-[95%] max-w-4xl mx-auto min-h-full pb-12">
        <button
          type="button"
          onClick={onBack}
          className="group inline-flex items-center gap-2 text-sm font-semibold text-slate-600 hover:text-blue-600 transition-colors"
        >
          <span className="text-base group-hover:-translate-x-0.5 transition-transform">←</span>
          로비로 돌아가기
        </button>

        <div className="mt-4">
          <SessionCreationForm />
        </div>
      </div>
    </div>
  );
}
