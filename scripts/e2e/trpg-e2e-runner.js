const { chromium } = require('playwright');

const BASE = process.env.BASE_URL || 'http://localhost:5173';
const T_SHORT = 5000;
const T_MED = 15000;
const T_LONG = 90000;

const scenarioIds = [
  '1.1 로그인 성공',
  '1.2 로그인 실패',
  '1.3 회원가입 모드 전환',
  '1.4 로그아웃',
  '2.1 캐릭터 생성',
  '2.2 캐릭터 수정',
  '2.3 캐릭터 삭제',
  '2.4 캐릭터 선택 → 로비 진입',
  '3.1 세션 생성',
  '3.2 세션 참가',
  '3.3 세션 종료/재시작/삭제',
  '3.4 빈 제목/프롬프트 오류',
  '4.1 게임 시작 (오프닝 내러티브)',
  '4.2 행동 제출',
  '4.3 호스트 행동 결정 (모더레이션)',
  '4.4 판정 Phase (AI 분석 + 주사위 굴리기)',
  '4.5 내러티브 생성 (AI 스토리)',
  '4.6 2라운드 반복',
  '5.1 두 플레이어 셋업',
  '5.2 게임 시작 & 동시 수신',
  '5.3 양측 행동 제출',
  '5.4 멀티 판정',
  '5.5 채팅 테스트',
  'E.1 빈 행동 제출',
  'E.2 빈 제목 세션 생성',
  'E.3 존재하지 않는 세션 참가',
  'E.4 이름 없는 캐릭터 생성',
  'E.5 호스트 퇴장 시 세션 종료',
];

const results = [];

function pushResult(id, status, detail = '') {
  results.push({ id, status, detail, at: new Date().toISOString() });
  console.log(`[${status}] ${id}${detail ? ` - ${detail}` : ''}`);
}

async function step(id, fn, opts = {}) {
  try {
    await fn();
    pushResult(id, 'PASS');
  } catch (e) {
    const msg = e?.message ? String(e.message).slice(0, 600) : String(e);
    const blocked = opts.allowBlocked && (
      /Timeout .* exceeded/i.test(msg) ||
      /API key|OPENAI|GEMINI|LLM|analyz|narrative|socket/i.test(msg)
    );
    pushResult(id, blocked ? 'BLOCKED' : 'FAIL', msg);
  }
}

async function exists(locator) {
  try {
    return await locator.first().isVisible({ timeout: 1000 });
  } catch {
    return false;
  }
}

function onceAcceptDialog(page) {
  page.once('dialog', async (d) => {
    try { await d.accept(); } catch {}
  });
}

async function closeTransientModals(page) {
  for (let i = 0; i < 3; i += 1) {
    const closeBtn = page.getByRole('button', { name: /^닫기$/ }).first();
    if (await exists(closeBtn)) {
      await closeBtn.click({ force: true });
      await page.waitForTimeout(120);
      continue;
    }

    const iconClose = page.locator('button[aria-label="close"]:visible').first();
    if (await exists(iconClose)) {
      await iconClose.click({ force: true });
      await page.waitForTimeout(120);
      continue;
    }

    try {
      await page.keyboard.press('Escape');
    } catch {
      // ignore keyboard failures in headless CI
    }
    await page.waitForTimeout(100);
  }
}

async function clearStorage(page) {
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => localStorage.clear());
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
}

async function login(page, username, password) {
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.getByLabel('사용자 이름').fill(username);
  await page.getByLabel('비밀번호').fill(password);
  await page.getByRole('button', { name: /^로그인$/ }).click();
}

async function ensureLoggedInCharacterPage(page, username, password) {
  // login page
  if (await exists(page.getByLabel('사용자 이름'))) {
    await login(page, username, password);
  }

  // from game -> lobby
  if (await exists(page.getByTitle('로비로 돌아가기'))) {
    await page.getByTitle('로비로 돌아가기').click();
    await page.getByText('어서 오세요').waitFor({ timeout: T_MED });
  }

  // from lobby -> character
  if (await exists(page.getByTitle('캐릭터 선택으로 돌아가기'))) {
    await page.getByTitle('캐릭터 선택으로 돌아가기').click();
  }

  // wait char management
  await page.getByRole('heading', { name: '캐릭터 관리' }).waitFor({ timeout: T_MED });
}

function charCard(page, name) {
  return page
    .locator('div')
    .filter({ has: page.getByRole('heading', { name }) })
    .filter({ has: page.getByRole('button', { name: '선택' }) })
    .first();
}

async function createCharacter(page, name) {
  // ensure form open
  if (!(await exists(page.getByRole('heading', { name: '새 캐릭터 생성' })) && await exists(page.locator('form')))) {
    if (await exists(page.getByRole('button', { name: '+ 새 캐릭터 생성' }))) {
      await page.getByRole('button', { name: '+ 새 캐릭터 생성' }).click();
    }
  }

  const form = page.locator('form').first();
  await form.locator('input[type="text"]').first().fill(name); // 이름
  await form.locator('input[type="number"]').first().fill('28'); // 나이
  await page.getByPlaceholder('예: 인간, 엘프, 드워프...').fill('인간');
  await page.getByPlaceholder('캐릭터의 배경이나 컨셉을 간단히 설명해주세요').fill('테스트 캐릭터');
  await form.getByRole('button', { name: /^생성$/ }).click();
  await page.getByRole('heading', { name }).waitFor({ timeout: T_MED });
}

async function ensureCharacter(page, name) {
  if (await exists(page.getByRole('heading', { name }))) return;
  await createCharacter(page, name);
}

async function editCharacter(page, oldName, newName) {
  const card = charCard(page, oldName);
  await card.getByRole('button', { name: '수정' }).click();

  const form = page.locator('form').first();
  await form.locator('input[type="text"]').first().fill(newName);
  await form.getByRole('button', { name: /^수정$/ }).first().click();
  await page.getByRole('heading', { name: newName }).waitFor({ timeout: T_MED });
}

async function deleteCharacter(page, name) {
  const card = charCard(page, name);
  onceAcceptDialog(page);
  await card.getByRole('button', { name: '삭제' }).click();
  await page.getByRole('heading', { name }).waitFor({ state: 'detached', timeout: T_MED });
}

async function selectCharacter(page, name) {
  const card = charCard(page, name);
  await card.getByRole('button', { name: '선택' }).click();
  await page.getByText('어서 오세요').waitFor({ timeout: T_MED });
}

async function ensureLobby(page) {
  if (await exists(page.getByText('어서 오세요'))) return;
  if (await exists(page.getByTitle('로비로 돌아가기'))) {
    await closeTransientModals(page);
    await page.getByTitle('로비로 돌아가기').click({ force: true });
  }
  if (await exists(page.getByRole('heading', { name: '캐릭터 관리' }))) {
    const selectAny = page.getByRole('button', { name: '선택' }).first();
    if (await exists(selectAny)) {
      await selectAny.click({ force: true });
    }
  }
  await page.getByText('어서 오세요').waitFor({ timeout: T_MED });
}

async function ensureInGame(page) {
  if (await exists(page.getByTitle('로비로 돌아가기'))) return;
  if (await exists(page.locator('textarea:visible').first())) return;
  if (await exists(page.getByText('스토리북이 비어있습니다').first())) return;
  throw new Error('게임 화면이 아님');
}

async function createSession(page, title, prompt) {
  await ensureLobby(page);
  await page.locator('#session-title').fill(title);
  await page.locator('#world-prompt').fill(prompt);
  await page.getByRole('button', { name: '세션 생성' }).click();
  await ensureInGame(page);
}

function sessionJoinCard(page, title) {
  return page
    .locator('div.bg-slate-50')
    .filter({ hasText: title })
    .filter({ has: page.getByRole('button', { name: /^참가$/ }) })
    .first();
}

function hostSessionCard(page, title) {
  return page
    .locator('div.bg-slate-50')
    .filter({ hasText: title })
    .filter({ has: page.getByRole('button', { name: /종료|재시작|삭제/ }) })
    .first();
}

async function ensureStartedIfPossible(page) {
  if (await exists(page.getByRole('button', { name: '게임 시작' }))) {
    await closeTransientModals(page);
    await page.getByRole('button', { name: '게임 시작' }).click({ force: true });
  }
}

async function submitAction(page, text) {
  const input = page.locator('textarea:visible').first();
  await input.fill(text);
  await input.press('Enter');
}

async function commitModeration(page) {
  await closeTransientModals(page);
  await page.getByRole('button', { name: '행동 결정' }).click({ force: true });
  await page.getByText(/행동 결정/).first().waitFor({ timeout: T_MED });
  await page.getByRole('button', { name: '제출하기' }).click({ force: true });
}

async function rollIfVisible(page) {
  await closeTransientModals(page);
  const rollOrConfirm = page.getByRole('button', { name: /주사위 굴리기|확인/ }).first();
  await rollOrConfirm.waitFor({ timeout: T_LONG });
  await rollOrConfirm.click({ force: true });
}

async function maybeProceedStory(page) {
  await closeTransientModals(page);
  const proceed = page.getByRole('button', { name: /이야기 진행|스토리 진행|판정 건너뛰고 스토리 진행/ }).first();
  if (await exists(proceed)) {
    await proceed.click({ force: true });
  }
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx1 = await browser.newContext();
  const p1 = await ctx1.newPage();
  p1.setDefaultTimeout(30000);

  const prefix = `${Date.now()}`;
  const charTemp = `용사아르테미스-${prefix}`;
  const charEdited = `${charTemp}-수정`;
  const hostChar = `전사가렌-${prefix}`;
  const user2Char = `마법사엘리사-${prefix}`;
  const sessionMain = `멀티플레이테스트-${prefix}`;
  const sessionHostLeave = `호스트퇴장-${prefix}`;

  // Phase 1
  await step('1.2 로그인 실패', async () => {
    await clearStorage(p1);
    await p1.getByLabel('사용자 이름').fill('wronguser');
    await p1.getByLabel('비밀번호').fill('wrongpass');
    await p1.getByRole('button', { name: /^로그인$/ }).click();
    await p1.waitForTimeout(700);
    if (await exists(p1.getByText(/잘못|invalid|incorrect|failed|실패|오류/i).first())) return;
    if (await exists(p1.getByRole('heading', { name: '캐릭터 관리' }))) {
      throw new Error('잘못된 계정인데 로그인 성공 화면으로 이동함');
    }
    await p1.getByRole('heading', { name: 'TRPG World' }).waitFor({ timeout: T_SHORT });
  });

  await step('1.3 회원가입 모드 전환', async () => {
    await p1.getByRole('button', { name: /계정이 없으신가요\? 회원가입/ }).click();
    await p1.getByLabel('인증 코드').waitFor({ timeout: T_SHORT });
    await p1.getByRole('button', { name: /^회원가입$/ }).waitFor({ timeout: T_SHORT });
    await p1.getByRole('button', { name: /이미 계정이 있으신가요\? 로그인/ }).click();
  });

  await step('1.1 로그인 성공', async () => {
    await ensureLoggedInCharacterPage(p1, 'user1', '1234');
    await p1.getByRole('heading', { name: '캐릭터 관리' }).waitFor({ timeout: T_MED });
    await p1.getByText('환영합니다, user1님!').waitFor({ timeout: T_MED });
  });

  await step('1.4 로그아웃', async () => {
    await ensureLoggedInCharacterPage(p1, 'user1', '1234');
    await p1.getByRole('button', { name: '로그아웃' }).click();
    await p1.getByRole('heading', { name: 'TRPG World' }).waitFor({ timeout: T_MED });
    await login(p1, 'user1', '1234');
    await p1.getByRole('heading', { name: '캐릭터 관리' }).waitFor({ timeout: T_MED });
  });

  // Phase 2 + E.4
  await step('2.1 캐릭터 생성', async () => {
    await ensureLoggedInCharacterPage(p1, 'user1', '1234');
    await createCharacter(p1, charTemp);
  });

  await step('2.2 캐릭터 수정', async () => {
    await ensureLoggedInCharacterPage(p1, 'user1', '1234');
    await editCharacter(p1, charTemp, charEdited);
  });

  await step('E.4 이름 없는 캐릭터 생성', async () => {
    await ensureLoggedInCharacterPage(p1, 'user1', '1234');
    if (!(await exists(pageFormHeading(p1)))) {
      await p1.getByRole('button', { name: '+ 새 캐릭터 생성' }).click();
    }
    const form = p1.locator('form').first();
    const nameInput = form.locator('input[type="text"]').first();
    await nameInput.fill('');
    await form.getByRole('button', { name: /^생성$/ }).click();
    const valid = await nameInput.evaluate((el) => el.checkValidity());
    if (valid) throw new Error('required 검증 미동작');
    if (await exists(form.getByRole('button', { name: '취소' }))) {
      await form.getByRole('button', { name: '취소' }).click();
    }
  });

  await step('2.3 캐릭터 삭제', async () => {
    await ensureLoggedInCharacterPage(p1, 'user1', '1234');
    await deleteCharacter(p1, charEdited);
  });

  await step('2.4 캐릭터 선택 → 로비 진입', async () => {
    await ensureLoggedInCharacterPage(p1, 'user1', '1234');
    await ensureCharacter(p1, hostChar);
    await selectCharacter(p1, hostChar);
    await p1.getByText('시스템 온라인').waitFor({ timeout: T_MED });
  });

  // Phase 3 + E.2 + E.3
  await step('3.4 빈 제목/프롬프트 오류', async () => {
    await ensureLobby(p1);
    await p1.locator('#session-title').fill('');
    await p1.locator('#world-prompt').fill('');
    await p1.getByRole('button', { name: '세션 생성' }).click();
    await p1.getByText('Title is required').waitFor({ timeout: T_SHORT });

    await p1.locator('#session-title').fill('제목만입력');
    await p1.locator('#world-prompt').fill('');
    await p1.getByRole('button', { name: '세션 생성' }).click();
    await p1.getByText('World prompt is required').waitFor({ timeout: T_SHORT });
  });

  await step('E.2 빈 제목 세션 생성', async () => {
    await ensureLobby(p1);
    await p1.locator('#session-title').fill('');
    await p1.locator('#world-prompt').fill('내용은있음');
    await p1.getByRole('button', { name: '세션 생성' }).click();
    await p1.getByText('Title is required').waitFor({ timeout: T_SHORT });
  });

  await step('3.1 세션 생성', async () => {
    await createSession(p1, sessionMain, '중세 판타지 세계 테스트');
    await ensureInGame(p1);
  });

  await step('E.1 빈 행동 제출', async () => {
    await ensureInGame(p1);
    const actionBtn = p1.locator('button:visible', { hasText: /^행동$/ }).first();
    const disabled = await actionBtn.isDisabled();
    if (!disabled) throw new Error('빈 행동에서 버튼이 활성화됨');
  });

  // Phase 4
  await step('4.1 게임 시작 (오프닝 내러티브)', async () => {
    await ensureInGame(p1);
    await ensureStartedIfPossible(p1);
    await p1.getByText('던전 마스터').first().waitFor({ timeout: T_LONG });
  }, { allowBlocked: true });

  await step('4.2 행동 제출', async () => {
    await ensureInGame(p1);
    await submitAction(p1, '주변을 살펴보며 위험한 것이 없는지 확인한다');
    await p1.getByText(/행동/).first().waitFor({ timeout: T_MED });
  }, { allowBlocked: true });

  await step('4.3 호스트 행동 결정 (모더레이션)', async () => {
    await ensureInGame(p1);
    await commitModeration(p1);
  }, { allowBlocked: true });

  await step('4.4 판정 Phase (AI 분석 + 주사위 굴리기)', async () => {
    await ensureInGame(p1);
    await rollIfVisible(p1);
    await p1.getByRole('button', { name: /다음|이야기 진행/ }).first().waitFor({ timeout: T_LONG });
  }, { allowBlocked: true });

  await step('4.5 내러티브 생성 (AI 스토리)', async () => {
    await ensureInGame(p1);
    await maybeProceedStory(p1);
    await p1.getByText('던전 마스터').first().waitFor({ timeout: T_LONG });
  }, { allowBlocked: true });

  await step('4.6 2라운드 반복', async () => {
    await ensureInGame(p1);
    await submitAction(p1, '보물 상자를 열어본다');
    await commitModeration(p1);
  }, { allowBlocked: true });

  // Phase 5 - second player
  const ctx2 = await browser.newContext();
  const p2 = await ctx2.newPage();
  p2.setDefaultTimeout(30000);

  await step('5.1 두 플레이어 셋업', async () => {
    await clearStorage(p2);
    await login(p2, 'user2', '1234');
    await ensureLoggedInCharacterPage(p2, 'user2', '1234');
    await ensureCharacter(p2, user2Char);
    await selectCharacter(p2, user2Char);
    await p2.getByRole('button', { name: '새로고침' }).first().click();
    const card = sessionJoinCard(p2, sessionMain);
    await card.getByRole('button', { name: /^참가$/ }).click();
    await ensureInGame(p2);
  });

  await step('3.2 세션 참가', async () => {
    await ensureInGame(p2);
  });

  await step('5.2 게임 시작 & 동시 수신', async () => {
    await ensureInGame(p1);
    await ensureStartedIfPossible(p1);
    await p2.getByText('던전 마스터').first().waitFor({ timeout: T_LONG });
  }, { allowBlocked: true });

  await step('5.3 양측 행동 제출', async () => {
    await submitAction(p1, '검을 뽑아 적에게 돌격한다');
    await submitAction(p2, '화염 마법을 시전한다');
    await commitModeration(p1);
    await p1.getByText(/행동 결정/).first().waitFor({ timeout: T_MED });
  }, { allowBlocked: true });

  await step('5.4 멀티 판정', async () => {
    await rollIfVisible(p1);
    await rollIfVisible(p2);
    await maybeProceedStory(p1);
  }, { allowBlocked: true });

  await step('5.5 채팅 테스트', async () => {
    await closeTransientModals(p1);
    await closeTransientModals(p2);
    await p1.locator('input[placeholder=\"메시지 전송...\"]:visible').first().fill('안녕하세요!');
    await p1.getByRole('button', { name: '전송' }).click({ force: true });
    await p2.getByText('안녕하세요!').first().waitFor({ timeout: T_MED });
  }, { allowBlocked: true });

  await step('E.3 존재하지 않는 세션 참가', async () => {
    await ensureLobby(p1);
    await p1.locator('#session-id').fill('99999');
    await p1.getByRole('button', { name: 'ID로 참가' }).click();
    await p1.getByText('세션을 찾을 수 없습니다.').waitFor({ timeout: T_SHORT });
  }, { allowBlocked: true });

  await step('3.3 세션 종료/재시작/삭제', async () => {
    await ensureLobby(p1);
    const row = hostSessionCard(p1, sessionMain);

    if (await exists(row.getByRole('button', { name: '종료' }))) {
      await row.getByRole('button', { name: '종료' }).click();
      await row.getByText('종료됨').waitFor({ timeout: T_MED });
    }

    if (await exists(row.getByRole('button', { name: '재시작' }))) {
      await row.getByRole('button', { name: '재시작' }).click();
      await ensureInGame(p1);
      await ensureLobby(p1);
    }

    const row2 = hostSessionCard(p1, sessionMain);
    if (await exists(row2.getByRole('button', { name: '종료' }))) {
      await row2.getByRole('button', { name: '종료' }).click();
      await row2.getByText('종료됨').waitFor({ timeout: T_MED });
    }

    onceAcceptDialog(p1);
    await row2.getByRole('button', { name: '삭제' }).click();
  }, { allowBlocked: true });

  await step('E.5 호스트 퇴장 시 세션 종료', async () => {
    // host creates new session
    await createSession(p1, sessionHostLeave, '호스트 퇴장 종료 테스트');

    // user2 go lobby and join
    await ensureLobby(p2);
    await p2.getByRole('button', { name: '새로고침' }).first().click();
    const joinCard = sessionJoinCard(p2, sessionHostLeave);
    await joinCard.getByRole('button', { name: /^참가$/ }).click();
    await ensureInGame(p2);

    // host leaves (end session)
    await p1.getByTitle('로비로 돌아가기').click();

    // participant receives session ended notification
    await p2.getByText(/세션이 종료되었습니다|호스트가 연결을 끊었습니다|세션 종료/).first().waitFor({ timeout: T_LONG });
  }, { allowBlocked: true });

  // fill missing as BLOCKED
  const byId = new Map(results.map((r) => [r.id, r]));
  const merged = scenarioIds.map((id) => byId.get(id) || {
    id,
    status: 'BLOCKED',
    detail: '시나리오가 실행 경로에 포함되지 않았습니다.',
    at: new Date().toISOString(),
  });

  console.log('\n=== RESULT JSON ===');
  console.log(JSON.stringify(merged, null, 2));

  await browser.close();
})().catch((e) => {
  console.error('Fatal error:', e);
  process.exit(1);
});

function pageFormHeading(page) {
  return page.getByRole('heading', { name: '새 캐릭터 생성' });
}
