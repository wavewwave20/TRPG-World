# TRPG World E2E 방법론 (재사용용)

이 문서는 `docs/playwright-mcp-test-plan.md` 기반 E2E를 다음에도 같은 방식으로 반복 실행하기 위한 표준 절차입니다.

## 1. 목표

- 로그인 → 캐릭터 → 세션 → 싱글/멀티 라운드 → 엣지 케이스까지 한 번에 검증
- 결과를 `PASS / FAIL / BLOCKED`로 고정 분류
- 실행 환경 차이(로컬 브라우저/패키지 문제)를 줄이기 위해 Playwright Docker 컨테이너 사용

## 2. 표준 실행 순서

프로젝트 루트에서 실행:

```bash
# 1) 이미지 빌드 + 컨테이너 기동 + 테스트 데이터 초기화 + E2E 실행
scripts/e2e/setup-and-run.sh
```

개별 실행:

```bash
# A. 서비스만 갱신
docker compose build backend frontend

docker compose up -d

# B. 테스트 데이터 초기화
scripts/e2e/reset-test-state.sh

# C. E2E 실행 (결과 로그 파일 경로 선택 가능)
scripts/e2e/run-e2e-docker.sh
scripts/e2e/run-e2e-docker.sh /tmp/trpg-e2e-latest.log
```

## 3. 스크립트 구성

- `scripts/e2e/trpg-e2e-runner.js`
  - 28개 시나리오를 순차 실행하고 마지막에 결과 JSON 출력
- `scripts/e2e/reset-test-state.sh`
  - `user1`, `user2` 관련 캐릭터/세션/스토리/판정 데이터 초기화
- `scripts/e2e/run-e2e-docker.sh`
  - Playwright Docker 컨테이너에서 runner 실행
- `scripts/e2e/setup-and-run.sh`
  - build/up/reset/run을 한 번에 수행

## 4. 결과 해석 규칙

- `PASS`: 기대 UI/이벤트 검증 성공
- `FAIL`: 기능/플로우 불일치, 셀렉터 충돌, 클릭 인터셉트 등 실제 실패
- `BLOCKED`: 선행 단계 실패, AI/소켓 대기 타임아웃, 의도된 가드에 의해 후속 단계 미진행

## 5. 운영 규칙

- 테스트 전에는 항상 `reset-test-state.sh` 실행
- 결과는 최소 1회 전체 실행 + 실패/블락 구간 보정 후 재실행
- 로그/결과 공유 시 `=== RESULT JSON ===` 블록 기준으로 보고

## 6. 알려진 관찰 포인트

- 판정 모달이 열려 있으면 로비/채팅/다른 버튼 클릭이 차단될 수 있음
- 싱글/멀티 라운드는 AI 응답과 소켓 이벤트 타이밍 영향이 큼
- `BLOCKED`는 종종 근본 원인 1개(예: 판정 완료 미전파)에서 연쇄 발생

## 7. 빠른 재실행 템플릿

```bash
scripts/e2e/reset-test-state.sh && scripts/e2e/run-e2e-docker.sh /tmp/trpg-e2e-rerun.log
```

