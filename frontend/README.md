# TRPG World - 프론트엔드

React + TypeScript + Vite 기반의 TRPG 게임 프론트엔드입니다.

## 목차

- [프로젝트 구조](#프로젝트-구조)
- [설치 및 실행](#설치-및-실행)
- [주요 기능](#주요-기능)
- [컴포넌트 구조](#컴포넌트-구조)
- [상태 관리](#상태-관리)
- [WebSocket 통신](#websocket-통신)
- [개발 가이드](#개발-가이드)

## 프로젝트 구조

```
frontend/
├── src/
│   ├── components/           # React 컴포넌트
│   │   ├── GameLayout.tsx           # 메인 게임 레이아웃
│   │   ├── JudgmentModal.tsx        # 판정 모달
│   │   ├── ActionButtons.tsx        # 행동 버튼
│   │   ├── ActiveJudgmentCard.tsx   # 활성 판정 카드
│   │   └── ...
│   │
│   ├── stores/               # Zustand 상태 관리
│   │   ├── socketStore.ts           # WebSocket 상태
│   │   ├── sessionStore.ts          # 세션 상태
│   │   └── authStore.ts             # 인증 상태
│   │
│   ├── services/             # API 서비스
│   │   ├── api.ts                   # Axios 인스턴스
│   │   ├── authService.ts           # 인증 API
│   │   ├── sessionService.ts        # 세션 API
│   │   └── characterService.ts      # 캐릭터 API
│   │
│   ├── types/                # TypeScript 타입
│   │   ├── socket.ts                # WebSocket 타입
│   │   ├── session.ts               # 세션 타입
│   │   └── character.ts             # 캐릭터 타입
│   │
│   ├── hooks/                # 커스텀 훅
│   ├── utils/                # 유틸리티 함수
│   ├── App.tsx               # 앱 진입점
│   └── main.tsx              # React 진입점
│
├── public/                   # 정적 파일
├── index.html                # HTML 템플릿
├── package.json              # 프로젝트 설정
├── vite.config.ts            # Vite 설정
├── tailwind.config.js        # Tailwind CSS 설정
└── README.md                 # 이 파일
```

## 설치 및 실행

### 1. 의존성 설치

```bash
npm install
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 다음 값들을 설정하세요:

```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=http://localhost:8000
```

### 3. 개발 서버 실행

```bash
npm run dev
```

브라우저에서 http://localhost:5173 으로 접속하세요.

### 4. 빌드

```bash
# 프로덕션 빌드
npm run build

# 빌드 미리보기
npm run preview
```

## 주요 기능

### 🎲 3단계 판정 시스템

#### Phase 1: 행동 제출
- 플레이어가 행동 입력
- 능력치 선택 (STR, DEX, CON, INT, WIS, CHA)
- 서버로 전송 → AI가 난이도 결정

#### Phase 2: 주사위 굴림
- 플레이어가 직접 주사위 굴림 (d20)
- 애니메이션 효과
- 실시간으로 다른 플레이어에게 공유

#### Phase 3: 결과 확인
- AI가 생성한 서술 표시
- 성공/실패 판정
- 다음 행동으로 진행

### 🌐 실시간 멀티플레이어

- WebSocket 기반 실시간 통신
- 참가자 목록 실시간 업데이트
- 다른 플레이어의 행동 실시간 확인
- 호스트 권한 시스템

### 🎨 UI/UX

- 반응형 디자인 (모바일, 태블릿, 데스크톱)
- 다크 모드 지원
- 부드러운 애니메이션
- 접근성 지원 (키보드 네비게이션, 스크린 리더)

## 컴포넌트 구조

### 주요 컴포넌트

#### GameLayout
메인 게임 화면 레이아웃

```tsx
<GameLayout>
  <LeftPane />      {/* 참가자 목록, 세션 정보 */}
  <CenterPane />    {/* 스토리 로그 */}
  <RightPane />     {/* 행동 입력, 판정 */}
</GameLayout>
```

#### JudgmentModal
판정 모달 (Phase 2, 3)

```tsx
<JudgmentModal>
  <JudgmentModalHeader />        {/* 헤더 */}
  <ActiveJudgmentCard />         {/* 현재 판정 */}
  <CompletedJudgmentsList />     {/* 완료된 판정 목록 */}
  <ActionButtons />              {/* 행동 버튼 */}
</JudgmentModal>
```

#### ActionButtons
상황에 따른 행동 버튼

- Phase 1: "행동 제출" 버튼
- Phase 2: "주사위 굴리기" 버튼
- Phase 3: "다음" / "이야기 진행" 버튼

### 컴포넌트 설계 원칙

1. **단일 책임**: 각 컴포넌트는 하나의 역할만 수행
2. **재사용성**: 공통 컴포넌트는 재사용 가능하게 설계
3. **타입 안전성**: TypeScript로 타입 정의
4. **접근성**: ARIA 속성 및 키보드 네비게이션 지원

## 상태 관리

Zustand를 사용하여 전역 상태를 관리합니다.

### socketStore

WebSocket 연결 및 이벤트 관리

```typescript
const { 
  socket,           // Socket.IO 인스턴스
  isConnected,      // 연결 상태
  connect,          // 연결
  disconnect,       // 연결 해제
  emit,             // 이벤트 전송
  on,               // 이벤트 리스너 등록
} = useSocketStore();
```

### sessionStore

세션 상태 관리

```typescript
const {
  currentSession,   // 현재 세션
  participants,     // 참가자 목록
  storyLogs,        // 스토리 로그
  judgments,        // 판정 목록
  setSession,       // 세션 설정
  addStoryLog,      // 스토리 로그 추가
} = useSessionStore();
```

### authStore

인증 상태 관리

```typescript
const {
  user,             // 현재 사용자
  token,            // JWT 토큰
  isAuthenticated,  // 인증 여부
  login,            // 로그인
  logout,           // 로그아웃
} = useAuthStore();
```

## WebSocket 통신

### 연결

```typescript
import { useSocketStore } from '@/stores/socketStore';

const { connect, disconnect } = useSocketStore();

// 연결
connect();

// 연결 해제
disconnect();
```

### 이벤트 전송

```typescript
const { emit } = useSocketStore();

// 세션 참가
emit('join_session', {
  session_id: 1,
  user_id: 1,
  character_id: 1
});

// 행동 제출
emit('submit_player_action', {
  session_id: 1,
  character_id: 1,
  action_text: '문을 연다',
  action_type: 'dexterity'
});
```

### 이벤트 수신

```typescript
const { on } = useSocketStore();

useEffect(() => {
  // 판정 준비 완료
  const unsubscribe = on('judgment_ready', (data) => {
    console.log('판정 준비:', data);
  });

  return () => unsubscribe();
}, [on]);
```

### 주요 이벤트

#### 클라이언트 → 서버

- `join_session` - 세션 참가
- `leave_session` - 세션 나가기
- `submit_player_action` - 행동 제출
- `roll_dice` - 주사위 굴림

#### 서버 → 클라이언트

- `judgment_ready` - 판정 준비 완료
- `dice_rolled` - 주사위 굴림 완료
- `story_generation_complete` - 서술 생성 완료
- `participant_joined` - 참가자 입장
- `participant_left` - 참가자 퇴장

## 개발 가이드

### 코드 스타일

ESLint와 Prettier를 사용하여 코드 스타일을 관리합니다:

```bash
# 린트 체크
npm run lint

# 자동 수정
npm run lint:fix

# 포맷팅
npm run format
```

### 타입 체크

```bash
# TypeScript 타입 체크
npm run type-check
```

### 컴포넌트 개발

새 컴포넌트를 만들 때:

1. `src/components/` 에 파일 생성
2. TypeScript로 타입 정의
3. Props 인터페이스 정의
4. 접근성 고려 (ARIA, 키보드)
5. 반응형 디자인 적용

```tsx
// 예시: Button.tsx
interface ButtonProps {
  children: React.ReactNode;
  onClick: () => void;
  variant?: 'primary' | 'secondary';
  disabled?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  onClick,
  variant = 'primary',
  disabled = false
}) => {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`btn btn-${variant}`}
      aria-disabled={disabled}
    >
      {children}
    </button>
  );
};
```

### 스타일링

Tailwind CSS를 사용합니다:

```tsx
// 기본 스타일
<div className="flex items-center justify-center p-4">

// 반응형
<div className="w-full md:w-1/2 lg:w-1/3">

// 다크 모드
<div className="bg-white dark:bg-gray-800">

// 호버 효과
<button className="hover:bg-blue-600 transition-colors">
```

### 커스텀 훅

재사용 가능한 로직은 커스텀 훅으로 분리:

```typescript
// useJudgment.ts
export const useJudgment = (judgmentId: number) => {
  const [judgment, setJudgment] = useState<Judgment | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 판정 데이터 로드
    loadJudgment(judgmentId).then(setJudgment);
    setLoading(false);
  }, [judgmentId]);

  return { judgment, loading };
};
```

## 반응형 디자인

### 브레이크포인트

```css
/* Tailwind 기본 브레이크포인트 */
sm: 640px   /* 모바일 가로 */
md: 768px   /* 태블릿 */
lg: 1024px  /* 데스크톱 */
xl: 1280px  /* 큰 데스크톱 */
2xl: 1536px /* 매우 큰 화면 */
```

### 테스트

```bash
# 개발자 도구에서 테스트
1. F12 또는 Ctrl+Shift+I
2. Ctrl+Shift+M (디바이스 툴바)
3. 다양한 화면 크기 테스트
```

## 접근성

### 키보드 네비게이션

- `Tab` / `Shift+Tab`: 포커스 이동
- `Enter` / `Space`: 버튼 클릭
- `Esc`: 모달 닫기
- `Arrow Keys`: 리스트 네비게이션

### 스크린 리더

- ARIA 레이블 사용
- 의미있는 HTML 태그 사용
- 포커스 관리

```tsx
<button
  aria-label="주사위 굴리기"
  aria-describedby="dice-help"
>
  🎲 굴리기
</button>
<span id="dice-help" className="sr-only">
  d20 주사위를 굴립니다
</span>
```

## 성능 최적화

### 코드 스플리팅

```typescript
// 라우트 기반 코드 스플리팅
const GamePage = lazy(() => import('./pages/GamePage'));
const SessionPage = lazy(() => import('./pages/SessionPage'));
```

### 메모이제이션

```typescript
// useMemo로 비용이 큰 계산 캐싱
const sortedJudgments = useMemo(() => {
  return judgments.sort((a, b) => a.id - b.id);
}, [judgments]);

// useCallback으로 함수 캐싱
const handleSubmit = useCallback(() => {
  submitAction(action);
}, [action]);
```

### 이미지 최적화

- WebP 포맷 사용
- Lazy loading
- 적절한 크기로 리사이징

## 트러블슈팅

### WebSocket 연결 실패

1. 백엔드 서버가 실행 중인지 확인
2. VITE_WS_URL이 올바른지 확인
3. CORS 설정 확인

### 빌드 오류

```bash
# node_modules 삭제 후 재설치
rm -rf node_modules
npm install

# 캐시 삭제
npm cache clean --force
```

### 타입 오류

```bash
# 타입 정의 업데이트
npm install --save-dev @types/node @types/react @types/react-dom
```

## 라이선스

MIT License
