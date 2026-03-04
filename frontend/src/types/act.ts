/**
 * Story Act system type definitions
 *
 * Defines types for the Act (막) transition system and
 * character growth rewards.
 */

export interface StoryActInfo {
  id: number;
  actNumber: number;
  title: string;
  subtitle: string | null;
  startedAt: string;
}

export interface GrowthReward {
  characterId: number;
  characterName: string;
  growthType: 'ability_increase' | 'new_skill';
  growthDetail: Record<string, any>;
  narrativeReason: string;
}

export interface ActTransitionResult {
  completedAct: StoryActInfo;
  newAct: StoryActInfo;
  growthRewards: GrowthReward[];
}

export interface ActGrowthHistory {
  actId: number;
  actNumber: number;
  actTitle: string;
  actSubtitle: string | null;
  rewards: GrowthReward[];
}
