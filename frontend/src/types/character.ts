/**
 * Character type definitions
 * 
 * Defines the structure of character data including D20 ability scores,
 * skills, weaknesses, and status effects.
 */

export type AbilityKey = 'strength' | 'dexterity' | 'constitution' | 'intelligence' | 'wisdom' | 'charisma';

export const ABILITY_LABELS: Record<AbilityKey, string> = {
  strength: '근력',
  dexterity: '민첩',
  constitution: '건강',
  intelligence: '지능',
  wisdom: '지혜',
  charisma: '매력',
};

export const ABILITY_SHORT_LABELS: Record<AbilityKey, string> = {
  strength: 'STR',
  dexterity: 'DEX',
  constitution: 'CON',
  intelligence: 'INT',
  wisdom: 'WIS',
  charisma: 'CHA',
};

export interface Skill {
  type?: string | 'passive' | 'active';
  name: string;
  description?: string;
  ability?: AbilityKey;
  cooldown_actions?: number;
}

export type StatusEffectCategory = 'physical' | 'mental';

export interface StatusEffect {
  name: string;
  category: StatusEffectCategory;
  severity: number;      // -3~+3 (음수=디버프, 양수=버프)
  modifier: number;      // 능력치 보정치에 적용되는 수치
  duration: number;      // 자동 회복까지 남은 페이즈 수 (0=영구)
  description?: string;
}

export type StatusType = 'buff' | 'debuff';

export interface UnifiedStatus {
  name: string;
  category: StatusEffectCategory | 'social' | 'environment';
  type: StatusType;
  modifier: number;
  source?: string;
  applies_to?: AbilityKey[] | 'all';
  description?: string;
}

export type InventoryItemType = 'consumable' | 'equipment';

export interface InventoryItem {
  name: string;
  quantity?: number;
  type?: InventoryItemType;
  equipped?: boolean;
  modifier?: number;
  status?: UnifiedStatus;
  action_modifiers?: Partial<Record<AbilityKey, number>>;
  description?: string;
}

export interface Weakness {
  name: string;
}

export interface CharacterData {
  inventory?: (string | InventoryItem)[];
  age?: number;
  race?: string;
  concept?: string;
  // D20 ability scores
  strength: number;
  dexterity: number;
  constitution: number;
  intelligence: number;
  wisdom: number;
  charisma: number;
  // Skills and modifiers
  skills: Skill[];
  weaknesses: (string | Weakness)[];
  status_effects: (string | StatusEffect)[];
  statuses?: UnifiedStatus[];
  skill_cooldowns?: Record<string, number>;
}

export interface Character {
  id: number;
  name: string;
  data: CharacterData;
}

/**
 * Calculate D20 ability modifier from ability score
 * Formula: floor((score - 10) / 2)
 * 
 * @param score - Ability score (1-30)
 * @returns Modifier value
 */
export function calculateModifier(score: number): number {
  return Math.floor((score - 10) / 2);
}

/**
 * Format ability score with modifier for display
 * Example: "STR 14 (+2)"
 * 
 * @param abilityName - Short name of the ability (e.g., "STR")
 * @param score - Ability score value
 * @returns Formatted string
 */
export function formatAbilityScore(abilityName: string, score: number): string {
  const modifier = calculateModifier(score);
  const sign = modifier >= 0 ? '+' : '';
  return `${abilityName} ${score} (${sign}${modifier})`;
}
