/**
 * API Service Layer
 * Handles all HTTP requests to the backend API
 */

// Base API URL - can be configured via environment variables
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Custom error class for API errors
 */
export class ApiError extends Error {
  statusCode: number;
  details?: any;

  constructor(
    message: string,
    statusCode: number,
    details?: any
  ) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.details = details;
  }
}

/**
 * Generic fetch wrapper with error handling
 */
async function fetchWithErrorHandling<T>(
  url: string,
  options?: RequestInit
): Promise<T> {
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    // Handle non-OK responses
    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      let errorDetails;

      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorData.message || errorMessage;
        errorDetails = errorData;
      } catch {
        // If response is not JSON, use status text
      }

      throw new ApiError(errorMessage, response.status, errorDetails);
    }

    // Parse JSON response
    const data = await response.json();
    return data as T;
  } catch (error) {
    // Re-throw ApiError as-is
    if (error instanceof ApiError) {
      throw error;
    }

    // Handle network errors
    if (error instanceof TypeError) {
      throw new ApiError(
        'Network error: Unable to connect to the server',
        0,
        error
      );
    }

    // Handle other errors
    throw new ApiError(
      error instanceof Error ? error.message : 'Unknown error occurred',
      0,
      error
    );
  }
}

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * Session creation request payload
 */
export interface CreateSessionRequest {
  host_user_id: number;
  title: string;
  world_prompt: string;
}

/**
 * Session creation response
 */
export interface CreateSessionResponse {
  session_id: number;
}

/**
 * Character creation request payload
 */
export interface CreateCharacterRequest {
  session_id: number;
  user_id: number;
  name: string;
}

import type { CharacterData } from '../types/character';

/**
 * Character data structure
 * Re-exported from types/character.ts for API compatibility
 */
export type { CharacterData };

/**
 * Character creation response
 */
export interface CreateCharacterResponse {
  id: number;
  user_id: number;
  name: string;
  data: CharacterData;
  created_at: string;
}

/**
 * Judgment summary for display in chat
 */
export interface JudgmentSummary {
  id: number;
  character_id: number;
  character_name: string;
  action_text: string;
  action_type: string | null;
  dice_result: number | null;
  modifier: number;
  final_value: number | null;
  difficulty: number;
  outcome: string | null;
}

/**
 * Story log entry structure
 */
export interface StoryLogEntry {
  id: number;
  role: 'USER' | 'AI';
  content: string;
  created_at: string;
  judgments?: JudgmentSummary[] | null;
}

/**
 * Story logs list response
 */
export interface StoryLogsResponse {
  session_id: number;
  logs: StoryLogEntry[];
}

/**
 * Session list item structure
 */
export interface SessionListItem {
  id: number;
  title: string;
  host_user_id: number;
  participant_count: number;
  created_at: string;
}

/**
 * Register request payload
 */
export interface RegisterRequest {
  username: string;
  password: string;
  access_code: string;
}

/**
 * Register response
 */
export interface RegisterResponse {
  user_id: number;
  username: string;
  message: string;
}

/**
 * Login request payload
 */
export interface LoginRequest {
  username: string;
  password: string;
}

/**
 * Login response
 */
export interface LoginResponse {
  user_id: number;
  username: string;
  message: string;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Create a new game session
 * 
 * @param sessionData - Session creation data
 * @returns Promise with the created session ID
 * @throws ApiError if validation fails or server error occurs
 * 
 * Requirements: 4.1, 4.2
 */
export async function createSession(
  sessionData: CreateSessionRequest
): Promise<CreateSessionResponse> {
  // Client-side validation (Requirements 4.1)
  if (!sessionData.title || sessionData.title.trim() === '') {
    throw new ApiError('Title is required', 400);
  }

  if (!sessionData.world_prompt || sessionData.world_prompt.trim() === '') {
    throw new ApiError('World prompt is required', 400);
  }

  const url = `${API_BASE_URL}/api/sessions`;
  
  return fetchWithErrorHandling<CreateSessionResponse>(url, {
    method: 'POST',
    body: JSON.stringify(sessionData),
  });
}

/**
 * Create a new character for a game session
 * 
 * @param characterData - Character creation data
 * @returns Promise with the created character details
 * @throws ApiError if validation fails or server error occurs
 * 
 * Requirements: 6.1, 6.2
 */
export async function createCharacter(
  characterData: CreateCharacterRequest
): Promise<CreateCharacterResponse> {
  // Client-side validation (Requirements 6.1)
  if (!characterData.name || characterData.name.trim() === '') {
    throw new ApiError('Character name is required', 400);
  }

  if (!characterData.session_id || characterData.session_id <= 0) {
    throw new ApiError('Valid session ID is required', 400);
  }

  if (!characterData.user_id || characterData.user_id <= 0) {
    throw new ApiError('Valid user ID is required', 400);
  }

  const url = `${API_BASE_URL}/api/characters`;
  
  return fetchWithErrorHandling<CreateCharacterResponse>(url, {
    method: 'POST',
    body: JSON.stringify(characterData),
  });
}

/**
 * Get all story logs for a game session
 * 
 * @param sessionId - ID of the game session
 * @returns Promise with the story logs in chronological order
 * @throws ApiError if session not found or server error occurs
 * 
 * Requirements: 7.5
 */
export async function getStoryLogs(
  sessionId: number
): Promise<StoryLogsResponse> {
  // Client-side validation
  if (!sessionId || sessionId <= 0) {
    throw new ApiError('Valid session ID is required', 400);
  }

  const url = `${API_BASE_URL}/api/story_logs/${sessionId}`;
  
  return fetchWithErrorHandling<StoryLogsResponse>(url, {
    method: 'GET',
  });
}

/**
 * Get list of all game sessions
 * 
 * @returns Promise with the list of sessions
 * @throws ApiError if server error occurs
 */
export async function getSessions(): Promise<SessionListItem[]> {
  const url = `${API_BASE_URL}/api/sessions`;
  
  return fetchWithErrorHandling<SessionListItem[]>(url, {
    method: 'GET',
  });
}

/**
 * Register a new user
 * 
 * @param registerData - Registration credentials with access code
 * @returns Promise with the registered user info
 * @throws ApiError if validation fails, access code is invalid, or username already exists
 */
export async function register(
  registerData: RegisterRequest
): Promise<RegisterResponse> {
  // Client-side validation
  if (!registerData.username || registerData.username.trim() === '') {
    throw new ApiError('Username is required', 400);
  }

  if (registerData.username.length < 3 || registerData.username.length > 50) {
    throw new ApiError('Username must be between 3 and 50 characters', 400);
  }

  if (!registerData.password || registerData.password.length < 4) {
    throw new ApiError('Password must be at least 4 characters', 400);
  }

  if (!registerData.access_code || registerData.access_code.trim() === '') {
    throw new ApiError('Access code is required', 400);
  }

  const url = `${API_BASE_URL}/api/auth/register`;
  
  return fetchWithErrorHandling<RegisterResponse>(url, {
    method: 'POST',
    body: JSON.stringify(registerData),
  });
}

/**
 * Login with existing credentials
 * 
 * @param loginData - Login credentials
 * @returns Promise with the user info
 * @throws ApiError if credentials are invalid
 */
export async function login(
  loginData: LoginRequest
): Promise<LoginResponse> {
  // Client-side validation
  if (!loginData.username || loginData.username.trim() === '') {
    throw new ApiError('Username is required', 400);
  }

  if (!loginData.password || loginData.password.trim() === '') {
    throw new ApiError('Password is required', 400);
  }

  const url = `${API_BASE_URL}/api/auth/login`;
  
  return fetchWithErrorHandling<LoginResponse>(url, {
    method: 'POST',
    body: JSON.stringify(loginData),
  });
}

/**
 * Get character by ID
 * 
 * @param characterId - ID of the character
 * @returns Promise with the character details
 * @throws ApiError if character not found or server error occurs
 */
export async function getCharacter(
  characterId: number
): Promise<CreateCharacterResponse> {
  if (!characterId || characterId <= 0) {
    throw new ApiError('Valid character ID is required', 400);
  }

  const url = `${API_BASE_URL}/api/characters/${characterId}`;
  
  return fetchWithErrorHandling<CreateCharacterResponse>(url, {
    method: 'GET',
  });
}
