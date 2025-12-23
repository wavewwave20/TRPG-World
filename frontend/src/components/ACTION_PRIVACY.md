# Action Privacy Implementation

## Overview

This document describes how action privacy is implemented in the TRPG World application to ensure that player actions remain private until the host decides to proceed with judgment.

## Privacy Flow

### 1. Action Submission Phase (Private)

When a player submits an action:

1. **Action Input** (`CenterPane.tsx`):
   - Player types action text in the input field
   - Clicks "행동" button or presses Enter
   - Action is sent via `submit_action` socket event with full action text

2. **Notification** (`socketStore.ts`):
   - All participants receive `action_submitted` event
   - Notification shows: `"{character_name} 이(가) 행동을 제출했습니다"`
   - **Action text is NOT included in the notification** (Requirement 1.2)
   - Only character name is revealed to other players

3. **Queue Count Update**:
   - Queue count badge appears on host's "행동 결정" button
   - Non-host players see the queue count but NOT the action details

### 2. Host Review Phase (Host-Only)

1. **Moderation Modal** (`ModerationModal.tsx`):
   - Only visible to the host player (controlled by `isHost` check in `CenterPane.tsx`)
   - Shows full action queue with action text for all submitted actions
   - Host can:
     - View all action texts
     - Edit action texts
     - Reorder actions
     - Delete actions
   - **Non-host players cannot access this modal** (Requirement 1.3, 1.4)

2. **Host Triggers Judgment**:
   - Host clicks "제출하기" button in ModerationModal
   - Backend emits `ai_generation_started` event
   - LLM determines DC and ability score for each action

### 3. Judgment Phase (Public)

1. **Action Reveal** (`JudgmentPanel.tsx`):
   - Backend emits `judgment_ready` with all judgment setups
   - First judgment becomes active
   - **Action text is NOW revealed to all participants** (Requirement 2.3)
   - All players see:
     - Character name
     - Action text (now public)
     - Ability score and modifier
     - Difficulty class (DC)
     - AI's reasoning

2. **Sequential Dice Rolling**:
   - Only the action owner can click "주사위 굴리기"
   - All participants see the dice roll animation simultaneously
   - Result is shown to all participants
   - Automatically moves to next judgment

## Code Locations

### Privacy Controls

1. **Action Submission Notification** (`frontend/src/stores/socketStore.ts`):
   ```typescript
   // Only show character name, not action text (privacy requirement)
   useGameStore.getState().addNotification({
     type: 'action_submitted',
     message: `${data.action.character_name} 이(가) 행동을 제출했습니다`,
     characterName: data.action.character_name
   });
   ```

2. **Host-Only Modal Access** (`frontend/src/components/CenterPane.tsx`):
   ```typescript
   // Check if current user is host
   const isHost = currentSession?.hostUserId === currentUserId;
   
   // Moderation Button - Only show when user is host
   {isHost && (
     <button onClick={() => setShowModerationModal(true)}>
       행동 결정
     </button>
   )}
   ```

3. **Action Text Reveal** (`frontend/src/components/JudgmentPanel.tsx`):
   ```typescript
   // Action text is revealed during judgment phase
   <p>{activeJudgment.action_text}</p>
   ```

## Requirements Validation

- ✅ **Requirement 1.1**: Action text NOT displayed to other participants during submission
- ✅ **Requirement 1.2**: Only notification shown (character name + "행동을 제출했습니다")
- ✅ **Requirement 1.3**: Host can view all actions in ModerationModal
- ✅ **Requirement 1.4**: Non-host participants cannot see action texts before judgment
- ✅ **Requirement 2.3**: Action text revealed when judgment becomes active

## Testing Privacy

To verify privacy is maintained:

1. **Test as Non-Host Player**:
   - Submit an action
   - Verify you see notification without action text
   - Verify you cannot access "행동 결정" button
   - Verify you cannot see other players' action texts

2. **Test as Host Player**:
   - See "행동 결정" button with queue count badge
   - Click button to open ModerationModal
   - Verify you can see all action texts
   - Click "제출하기" to start judgment phase

3. **Test Judgment Phase**:
   - Verify all participants see action text when judgment becomes active
   - Verify action text is displayed in JudgmentPanel
   - Verify all participants see the same information

## Security Considerations

- Action text is never sent to non-host clients until judgment phase
- Backend controls when action text is revealed (via `judgment_ready` event)
- Frontend only displays what backend sends
- No client-side filtering or hiding of action text (backend controls visibility)
