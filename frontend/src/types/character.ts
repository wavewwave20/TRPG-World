/**
 * Character type definitions
 * 
 * Defines the structure of character data including D20 ability scores,
 * skills, weaknesses, and status effects.
 */

export interface Skill {
  type?: string | 'passive' | 'active';
  name: string;
  description?: string;
}

export interface CharacterData {
  inventory?: string[];
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
  weaknesses: string[];
  status_effects: string[];
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
