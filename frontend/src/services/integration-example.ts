/**
 * Integration Examples
 * 
 * This file demonstrates how to integrate the API service with Zustand stores
 * and Socket.io for complete session and character creation flows.
 */

import { createSession, createCharacter, ApiError } from './api';
import { useGameStore } from '../stores/gameStore';
import { useSocketStore } from '../stores/socketStore';

/**
 * Example: Complete session creation flow
 * 
 * 1. Create session via API
 * 2. Update game store with session data
 * 3. Join session via socket
 */
export async function handleSessionCreation(
  hostUserId: number,
  characterId: number,
  title: string,
  worldPrompt: string
): Promise<void> {
  try {
    // Step 1: Create session via API (Requirements 4.1, 4.2)
    const response = await createSession({
      host_user_id: hostUserId,
      title,
      world_prompt: worldPrompt,
    });

    // Step 2: Update game store
    const { setSession } = useGameStore.getState();
    setSession({
      id: response.session_id,
      title,
      hostUserId,
    });

    // Step 3: Join session via socket (for next task)
    const { emit } = useSocketStore.getState();
    emit('join_session', {
      session_id: response.session_id,
      user_id: hostUserId,
      character_id: characterId,
    });

    console.log('Session created and joined:', response.session_id);
  } catch (error) {
    if (error instanceof ApiError) {
      console.error('Failed to create session:', error.message);
      throw error;
    }
    throw error;
  }
}

/**
 * Example: Complete character creation flow
 * 
 * 1. Create character via API
 * 2. Update game store with character data
 */
export async function handleCharacterCreation(
  sessionId: number,
  userId: number,
  characterName: string
): Promise<void> {
  try {
    // Step 1: Create character via API (Requirements 6.1, 6.2)
    const response = await createCharacter({
      session_id: sessionId,
      user_id: userId,
      name: characterName,
    });

    // Step 2: Update game store
    const { setCharacter } = useGameStore.getState();
    setCharacter({
      id: response.id,
      name: response.name,
      data: response.data,
    });

    console.log('Character created:', response.id);
  } catch (error) {
    if (error instanceof ApiError) {
      console.error('Failed to create character:', error.message);
      throw error;
    }
    throw error;
  }
}
