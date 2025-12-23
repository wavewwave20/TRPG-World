/**
 * Judgment Data Types
 * 
 * These types define the structure for AI-driven action judgments
 * in the TRPG system, including dice rolls and outcomes.
 */

/**
 * Status of a judgment in the sequential judgment flow
 */
export type JudgmentStatus = 'waiting' | 'active' | 'rolling' | 'complete';

/**
 * Outcome of a dice roll judgment
 */
export type JudgmentOutcome = 'critical_failure' | 'failure' | 'success' | 'critical_success';

/**
 * D20 ability scores
 */
export type AbilityScore = 'str' | 'dex' | 'con' | 'int' | 'wis' | 'cha';

/**
 * Initial judgment setup received from the backend
 * Contains all information needed for a player to roll dice
 */
export interface JudgmentSetup {
  /** Unique identifier for the action being judged */
  action_id: number;
  
  /** ID of the character performing the action */
  character_id: number;
  
  /** Name of the character performing the action */
  character_name: string;
  
  /** The action text submitted by the player */
  action_text: string;
  
  /** Which ability score is being tested (str/dex/con/int/wis/cha) */
  ability_score: AbilityScore;
  
  /** Modifier value to add to the dice roll */
  modifier: number;
  
  /** Difficulty Class - the target number to meet or exceed */
  difficulty: number;
  
  /** AI's explanation for why this DC and ability score were chosen */
  difficulty_reasoning: string;
  
  /** Current status of this judgment in the sequence */
  status: JudgmentStatus;
  
  /** Order in the judgment sequence (0-indexed) */
  order: number;
}

/**
 * Complete judgment result after dice have been rolled
 * Extends JudgmentSetup with the dice roll results and outcome
 */
export interface JudgmentResult extends JudgmentSetup {
  /** The raw dice roll result (1-20) */
  dice_result: number;
  
  /** Final value after adding modifier (dice_result + modifier) */
  final_value: number;
  
  /** The outcome of the judgment based on the roll vs DC */
  outcome: JudgmentOutcome;
  
  /** AI's explanation for the outcome */
  outcome_reasoning: string;
}
