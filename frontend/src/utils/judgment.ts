import type { AbilityScore } from '../types/judgment';

/**
 * 백엔드 action_type 문자열을 AbilityScore 코드로 변환하는 매핑
 */
export const ACTION_TYPE_TO_ABILITY: Record<string, AbilityScore> = {
  strength: 'str',
  dexterity: 'dex',
  constitution: 'con',
  intelligence: 'int',
  wisdom: 'wis',
  charisma: 'cha',
};

/**
 * AbilityScore 코드를 한글 능력치명으로 변환하는 매핑
 */
export const ABILITY_NAMES_KO: Record<string, string> = {
  str: '근력',
  dex: '민첩',
  con: '건강',
  int: '지능',
  wis: '지혜',
  cha: '매력',
};

/**
 * 한글 능력치명을 반환합니다.
 */
export function getAbilityNameKo(ability: string): string {
  return ABILITY_NAMES_KO[ability] || ability.toUpperCase();
}

/**
 * action_type 문자열에서 AbilityScore를 결정합니다.
 * 매핑에 없는 경우 기본값 'dex'를 반환합니다.
 */
export function resolveAbilityScore(actionType: string | undefined): AbilityScore {
  return ACTION_TYPE_TO_ABILITY[actionType ?? ''] ?? 'dex';
}

/**
 * 주사위 굴림 필요 여부를 결정합니다.
 * difficulty <= 0이면 자동 성공(false)으로 처리합니다.
 */
export function computeRequiresRoll(
  difficulty: number,
  requiresRoll?: unknown
): boolean {
  const normalizedDifficulty = Number(difficulty);
  if (Number.isFinite(normalizedDifficulty) && normalizedDifficulty <= 0) return false;

  if (typeof requiresRoll === 'boolean') return requiresRoll;
  if (typeof requiresRoll === 'number') return requiresRoll !== 0;
  if (typeof requiresRoll === 'string') {
    const normalized = requiresRoll.trim().toLowerCase();
    if (['false', '0', 'no', 'off', 'n'].includes(normalized)) return false;
    if (['true', '1', 'yes', 'on', 'y'].includes(normalized)) return true;
  }

  return true;
}
