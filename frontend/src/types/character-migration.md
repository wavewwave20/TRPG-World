# Character Data Model Extension - Migration Guide

## Overview
Extended the Character data model to include D20 ability scores, skills, weaknesses, and status effects as per Requirements 6.1, 6.4, 6.5, 6.6.

## Changes Made

### 1. New Type Definitions (`frontend/src/types/character.ts`)
Created a centralized type definition file with:
- `Skill` interface: Defines skill structure with optional type, name, and description
- `CharacterData` interface: Complete character data including:
  - Existing fields: HP, MP, inventory
  - New optional fields: age, race, concept
  - D20 ability scores: strength, dexterity, constitution, intelligence, wisdom, charisma
  - Skills, weaknesses, and status_effects arrays
- `Character` interface: Base character structure with id, name, and data
- `calculateModifier()` function: Calculates D20 modifier from ability score
- `formatAbilityScore()` function: Formats ability score with modifier for display

### 2. Updated Store (`frontend/src/stores/gameStore.ts`)
- Imported Character type from shared types
- Removed local Character interface definition
- Now uses centralized type definition

### 3. Updated API Service (`frontend/src/services/api.ts`)
- Imported and re-exported CharacterData type from shared types
- Removed local CharacterData interface definition
- Maintains API compatibility while using shared types

### 4. Updated Components

#### `frontend/src/App.tsx`
- Imported base Character type
- Extended Character interface to include API-specific fields (user_id, created_at)
- Simplified handleSelectCharacter to pass entire character.data object

#### `frontend/src/components/CharacterManagement.tsx`
- Imported base Character and Skill types
- Maintained local Character interface for component-specific needs
- Updated onSelectCharacter prop type to accept base Character type

## New Fields Added

### D20 Ability Scores (Required)
- `strength: number` - Physical power (1-30)
- `dexterity: number` - Agility and reflexes (1-30)
- `constitution: number` - Endurance and health (1-30)
- `intelligence: number` - Knowledge and reasoning (1-30)
- `wisdom: number` - Perception and insight (1-30)
- `charisma: number` - Social influence (1-30)

### Character Details (Optional)
- `age?: number` - Character age
- `race?: string` - Character race/species
- `concept?: string` - Character concept/background

### Skills and Modifiers (Required)
- `skills: Skill[]` - Array of character skills
- `weaknesses: string[]` - Array of character weaknesses
- `status_effects: string[]` - Array of active status effects

## Utility Functions

### calculateModifier(score: number): number
Calculates the D20 ability modifier from an ability score.
- Formula: `Math.floor((score - 10) / 2)`
- Example: score 14 → modifier +2

### formatAbilityScore(abilityName: string, score: number): string
Formats an ability score with its modifier for display.
- Example: `formatAbilityScore("STR", 14)` → "STR 14 (+2)"

## Backward Compatibility
All new fields (except D20 ability scores) are optional or have default values, ensuring backward compatibility with existing character data. Components that don't use the new fields will continue to work without modification.

## Next Steps
Task 14 will create a CharacterStatsPanel component to display these new ability scores in the game interface.
