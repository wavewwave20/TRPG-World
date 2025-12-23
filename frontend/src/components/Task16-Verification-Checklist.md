# Task 16 검증 체크리스트

## 코드 검증 ✅

### 1. aria-live 영역 추가
- [x] JudgmentModal.tsx에 판정 업데이트 공지 영역 추가
- [x] JudgmentModal.tsx에 진행 상황 공지 영역 추가
- [x] ResultDisplay.tsx에 주사위 결과 공지 영역 추가
- [x] aria-live="polite" 사용 (일반 업데이트)
- [x] aria-live="assertive" 사용 (중요한 결과)

### 2. 주사위 결과 공지
- [x] ResultDisplay에 getOutcomeAnnouncement 함수 구현
- [x] 주사위 값, 보정치, 최종 값, 결과 포함
- [x] sr-only 클래스로 시각적으로 숨김

### 3. 판정 전환 공지
- [x] JudgmentModal에 getJudgmentAnnouncement 함수 구현
- [x] Active/Rolling/Complete 상태별 메시지
- [x] 현재 플레이어 여부에 따른 메시지 변경

### 4. 버튼 aria-label
- [x] ActionButtons - 주사위 굴리기 버튼
- [x] ActionButtons - 다음 판정 버튼
- [x] ActionButtons - 이야기 진행 버튼
- [x] aria-disabled 속성 추가
- [x] 버튼 그룹에 role="group" 추가

### 5. 카드 aria-label
- [x] ActiveJudgmentCard - 카드 전체 (role="article")
- [x] ActiveJudgmentCard - 캐릭터 아바타 (role="img")
- [x] ActiveJudgmentCard - 행동 내용 (role="region")
- [x] ActiveJudgmentCard - 판정 정보 (role="region")
- [x] ActiveJudgmentCard - 능력치 카드 (role="group")
- [x] ActiveJudgmentCard - 난이도 카드 (role="group")
- [x] ActiveJudgmentCard - 주사위 굴림 중 (role="status")

### 6. ResultDisplay aria-label
- [x] 결과 영역 (role="region")
- [x] 주사위 결과 그룹 (role="group")
- [x] 주사위 값 aria-label
- [x] 최종 값 aria-label (계산 포함)
- [x] 결과 카드 (role="alert")

### 7. CompletedJudgmentsList aria-label
- [x] 목록 영역 (role="region")
- [x] 목록 컨테이너 (role="list")
- [x] 각 항목 (role="listitem")
- [x] 확장/축소 버튼 aria-expanded
- [x] 확장/축소 버튼 aria-controls
- [x] 확장/축소 버튼 상세 aria-label
- [x] 상세 정보 영역 (role="region")
- [x] 능력치/난이도/주사위 결과 (role="group")

### 8. WaitingIndicator aria-label
- [x] 대기 영역 (role="status")
- [x] 개수 배지 aria-label
- [x] 캐릭터 목록 (role="list")
- [x] 각 캐릭터 (role="listitem")
- [x] 캐릭터 아바타 (role="img")

### 9. CSS 클래스
- [x] sr-only 클래스 추가 (index.css)
- [x] 시각적으로 숨기지만 스크린 리더에서 읽기 가능

### 10. 컴파일 검증
- [x] JudgmentModal.tsx - 오류 없음
- [x] ActiveJudgmentCard.tsx - 오류 없음
- [x] ActionButtons.tsx - 오류 없음
- [x] ResultDisplay.tsx - 오류 없음
- [x] CompletedJudgmentsList.tsx - 오류 없음
- [x] WaitingIndicator.tsx - 오류 없음

## 수동 테스트 체크리스트

### 스크린 리더 테스트 (NVDA/VoiceOver)

#### 모달 열림
- [ ] "판정 진행 상황: 1번째 판정, 총 X개 중" 공지 확인
- [ ] "{캐릭터명}의 판정 차례입니다" 공지 확인
- [ ] 포커스가 첫 번째 버튼으로 이동 확인

#### 주사위 굴림
- [ ] "주사위를 굴리는 중입니다" 공지 확인
- [ ] "판정 결과: 주사위 X, 보정치 +Y, 최종 값 Z, 성공/실패" 공지 확인
- [ ] 결과가 즉시 공지되는지 확인 (aria-live="assertive")

#### 판정 전환
- [ ] "판정 진행 상황: 2번째 판정..." 공지 확인
- [ ] 다음 캐릭터 정보 공지 확인

#### 버튼 탐색
- [ ] Tab 키로 모든 버튼 접근 가능
- [ ] 각 버튼의 aria-label이 명확하게 읽힘
- [ ] 비활성화된 버튼의 상태가 공지됨

#### 완료된 판정 탐색
- [ ] 완료된 판정 목록이 "list"로 인식됨
- [ ] 각 항목이 "listitem"으로 인식됨
- [ ] 확장/축소 버튼의 상태가 공지됨
- [ ] 확장 시 상세 정보가 읽힘

#### 대기 중 판정
- [ ] 대기 중인 판정 수가 공지됨
- [ ] 대기 중인 캐릭터 목록이 읽힘

### 키보드 네비게이션 테스트

#### 기본 탐색
- [ ] Tab: 다음 요소로 이동
- [ ] Shift + Tab: 이전 요소로 이동
- [ ] Enter: 버튼 클릭
- [ ] Space: 버튼 클릭
- [ ] Esc: 모달 닫기 (완료 시에만)

#### 포커스 트랩
- [ ] Tab 키로 모달 외부로 포커스 이동 불가
- [ ] 모달 내 모든 요소 순환 탐색 가능

#### 완료된 판정
- [ ] Enter/Space로 확장/축소 가능
- [ ] 확장된 상태에서 Tab으로 내부 요소 탐색 불가 (버튼만 포커스)

### 브라우저 개발자 도구 테스트

#### Chrome DevTools
- [ ] Elements → Accessibility 패널 확인
- [ ] 모든 요소에 적절한 role 속성
- [ ] 모든 버튼에 accessible name
- [ ] aria-live 영역 확인

#### Lighthouse 감사
- [ ] Accessibility 점수 90+ 확인
- [ ] ARIA 속성 검증 통과
- [ ] 대비율 검증 통과

### 실제 사용 시나리오

#### 시나리오 1: 첫 판정
1. [ ] 모달 열림 공지
2. [ ] 현재 캐릭터 정보 공지
3. [ ] 주사위 굴리기 버튼 포커스
4. [ ] Enter로 주사위 굴림
5. [ ] 결과 공지
6. [ ] 다음 버튼 활성화

#### 시나리오 2: 중간 판정
1. [ ] 진행 상황 업데이트 공지
2. [ ] 다음 캐릭터 정보 공지
3. [ ] 대기 중인 판정 수 공지

#### 시나리오 3: 마지막 판정
1. [ ] 마지막 판정 완료 공지
2. [ ] "이야기 진행" 버튼 활성화
3. [ ] 버튼 레이블에 "모든 판정 완료" 포함

#### 시나리오 4: 완료된 판정 확인
1. [ ] Tab으로 완료된 판정 버튼 이동
2. [ ] 각 판정의 요약 정보 읽기
3. [ ] Enter로 확장
4. [ ] 상세 정보 읽기
5. [ ] Enter로 축소

## 요구사항 검증

### 요구사항 6.3: 스크린 리더 변경 사항 알림
- [x] aria-live 영역으로 판정 업데이트 공지
- [x] 주사위 결과 공지
- [x] 판정 전환 공지
- [x] 버튼 및 카드에 적절한 aria-label

## 접근성 표준 검증

### WCAG 2.1 AA
- [x] 1.3.1 Info and Relationships (Level A)
- [x] 2.1.1 Keyboard (Level A)
- [x] 4.1.2 Name, Role, Value (Level A)
- [x] 4.1.3 Status Messages (Level AA)

### ARIA 1.2
- [x] role 속성 적절히 사용
- [x] aria-live 적절히 사용
- [x] aria-label 명확하게 작성
- [x] aria-expanded, aria-controls 적절히 사용

## 문서화
- [x] Task16-ScreenReader-Support.md 작성
- [x] 모든 변경사항 문서화
- [x] 테스트 방법 문서화
- [x] 검증 체크리스트 작성

## 최종 확인
- [x] 모든 컴포넌트 컴파일 성공
- [x] TypeScript 오류 없음
- [x] 코드 리뷰 완료
- [ ] 스크린 리더 테스트 완료 (사용자 수동 테스트 필요)
- [ ] 실제 사용자 피드백 수집 (선택사항)

---

**참고:** 스크린 리더 테스트는 실제 스크린 리더 소프트웨어(NVDA, VoiceOver 등)를 사용하여 수동으로 진행해야 합니다.
