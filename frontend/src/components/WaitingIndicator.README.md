# WaitingIndicator Component

## Overview

The `WaitingIndicator` component displays the number of judgments that are still waiting to be processed in the judgment queue. It provides players with awareness of how many judgments remain after the current one.

## Features

- **Count Display**: Shows the number of waiting judgments with a badge
- **Visual Indicator**: Uses an hourglass icon (⏳) to represent waiting status
- **Character Preview**: For 3 or fewer waiting judgments, shows character names and avatars
- **Responsive Design**: Adapts to mobile and desktop screen sizes
- **Conditional Rendering**: Only displays when there are waiting judgments

## Requirements Satisfied

- **4.2**: Display the number of waiting judgments

## Props

```typescript
interface WaitingIndicatorProps {
  /** Array of judgments that are still waiting to be processed */
  waitingJudgments: JudgmentSetup[];
}
```

## Usage

```tsx
import WaitingIndicator from './WaitingIndicator';
import type { JudgmentSetup } from '../types/judgment';

function MyComponent() {
  const waitingJudgments: JudgmentSetup[] = [
    // ... judgments with status 'waiting' or 'active'
  ];

  return (
    <WaitingIndicator waitingJudgments={waitingJudgments} />
  );
}
```

## Integration in JudgmentModal

The component is integrated into the `JudgmentModal` between the active judgment card and the completed judgments list:

```tsx
// Get waiting judgments (all judgments after current index)
const waitingJudgments = judgments
  .slice(currentJudgmentIndex + 1)
  .filter((j): j is JudgmentSetup => j.status === 'waiting' || j.status === 'active');

// Render in modal
<WaitingIndicator waitingJudgments={waitingJudgments} />
```

## Visual Design

### Layout Structure

```
┌─────────────────────────────────────┐
│  ⏳  대기 중인 판정              [3] │
│      3개의 판정이 대기 중입니다      │
│  ─────────────────────────────────  │
│  👤 캐릭터1                          │
│  👤 캐릭터2                          │
│  👤 캐릭터3                          │
└─────────────────────────────────────┘
```

### Color Scheme

- **Background**: Slate-50 (`bg-slate-50`)
- **Border**: Slate-200 (`border-slate-200`)
- **Icon Background**: Slate-200 (`bg-slate-200`)
- **Badge Background**: Slate-300 (`bg-slate-300`)
- **Text**: Slate-700 for title, Slate-600 for description

## Responsive Behavior

### Mobile (< 640px)
- Smaller icon size (40px)
- Smaller badge size (32px)
- Smaller text sizes
- Compact padding

### Desktop (≥ 640px)
- Larger icon size (48px)
- Larger badge size (40px)
- Larger text sizes
- More generous padding

## Character Preview Feature

When there are 3 or fewer waiting judgments, the component displays a preview list showing:
- Character avatar (first letter of name)
- Character name (truncated if too long)

This helps players see who's up next without cluttering the interface.

## Accessibility

- **Icon Label**: The hourglass icon has `aria-label="대기 중"` for screen readers
- **Semantic HTML**: Uses proper div structure with clear hierarchy
- **Text Contrast**: All text meets WCAG AA contrast requirements

## Example States

### No Waiting Judgments
Component returns `null` and doesn't render anything.

### 1 Waiting Judgment
```
⏳ 대기 중인 판정 [1]
   1개의 판정이 대기 중입니다
   ─────────────────────
   👤 전사
```

### 4+ Waiting Judgments
```
⏳ 대기 중인 판정 [5]
   5개의 판정이 대기 중입니다
```
(Character preview is hidden when more than 3 judgments)

## Testing Considerations

### Unit Tests
- Renders correctly with waiting judgments
- Returns null when no waiting judgments
- Shows character preview for ≤3 judgments
- Hides character preview for >3 judgments
- Displays correct count

### Integration Tests
- Updates when judgments progress
- Filters correctly based on judgment status
- Integrates properly with JudgmentModal

## Performance

- **Conditional Rendering**: Returns null early if no waiting judgments
- **Simple Structure**: Minimal DOM elements
- **No State**: Stateless component, relies on props only
- **Efficient Filtering**: Uses array slice and filter operations

## Future Enhancements

Potential improvements for future iterations:
1. Animation when count changes
2. Hover tooltip showing all waiting character names
3. Click to preview waiting judgment details
4. Progress bar showing position in queue
5. Estimated time remaining (if applicable)
