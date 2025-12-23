# Accessibility Features Documentation

This document outlines the accessibility features implemented in the frontend AI integration components.

## Overview

All components have been enhanced with comprehensive accessibility features following WCAG 2.1 Level AA guidelines. These enhancements ensure that users with disabilities can fully interact with the AI judgment system using assistive technologies.

## Components

### 1. JudgmentPanel Component

#### ARIA Labels and Roles
- **Panel Container**: `role="region"` with `aria-label="판정 패널"`
- **Progress Indicator**: `role="status"` with descriptive `aria-label`
- **Active Judgment**: `role="article"` with `aria-labelledby` and `aria-describedby`
- **Completed Judgments**: `role="region"` with proper heading structure
- **Waiting Count**: `role="status"` for dynamic updates

#### Screen Reader Announcements
- Live region (`role="status"`, `aria-live="polite"`) announces:
  - New judgment progression
  - Character name and action
  - Ability score and difficulty
  - Dice roll results and outcomes
- Announcements are atomic (`aria-atomic="true"`) for complete context

#### Keyboard Navigation
- **Roll Button**: Full keyboard support with focus management
  - Automatically receives focus when it's the player's turn
  - `Tab` key navigation
  - `Enter` or `Space` to activate
  - Visible focus indicator (`focus:ring-2`)
- **Completed Judgments**: 
  - Expandable/collapsible with keyboard (`Enter` or `Space`)
  - `aria-expanded` state properly managed
  - `aria-controls` links to expanded content

#### Focus Management
- Roll button automatically receives focus when judgment becomes active
- Focus is managed programmatically using `useRef` and `useEffect`
- Active judgment scrolls into view smoothly
- Focus indicators are clearly visible

#### Semantic HTML
- Proper heading hierarchy (`h3`, `h4`)
- Descriptive labels for all interactive elements
- Unique IDs for label associations
- Proper button elements (not divs with click handlers)

### 2. DiceRollAnimation Component

#### ARIA Labels and Roles
- **Container**: `role="status"` with `aria-live="polite"`
- **Dice Icon**: `aria-label="주사위 굴리는 중"` during rolling phase
- **Result Display**: Descriptive `aria-label` with result and outcome

#### Screen Reader Announcements
- Announces "주사위를 굴리는 중" when animation starts
- Announces result with context:
  - "대성공! 주사위 결과 20" for critical success
  - "대실패! 주사위 결과 1" for critical failure
  - "주사위 결과 [number]" for normal rolls
- Uses `sr-only` class for screen reader-only text

#### Visual Indicators
- Decorative elements marked with `aria-hidden="true"`
- Result value has both visual and auditory feedback

### 3. AIGenerationIndicator Component

#### ARIA Labels and Roles
- **Container**: `role="alert"` with `aria-live="assertive"`
- **Busy State**: `aria-busy="true"` indicates loading
- **Message**: Descriptive `aria-label` and `id` for associations

#### Screen Reader Announcements
- Assertive live region ensures immediate announcement
- Loading message is clearly communicated
- Decorative animations marked with `aria-hidden="true"`

#### Visual Design
- High contrast text on white background
- Loading spinner with multiple visual cues
- Animated dots provide additional visual feedback

### 4. CharacterStatsPanel Component

#### ARIA Labels and Roles
- **Panel Container**: `role="region"` with character name label
- **Ability Scores**: `role="group"` with descriptive labels
- **Skills Section**: `role="region"` with expandable/collapsible button
- **Lists**: Proper `role="list"` and `role="listitem"` for skills, weaknesses, and status effects

#### Keyboard Navigation
- **Skills Toggle**: 
  - Full keyboard support (`Enter` or `Space`)
  - `aria-expanded` state management
  - `aria-controls` links to skills list
  - Visible focus indicator

#### Semantic Structure
- Proper heading hierarchy
- Descriptive labels for all sections
- Ability scores include both value and modifier in labels
- Skills include type (passive/active) in labels

## Testing Recommendations

### Screen Reader Testing
Test with the following screen readers:
- **Windows**: NVDA (free) or JAWS
- **macOS**: VoiceOver (built-in)
- **Mobile**: TalkBack (Android) or VoiceOver (iOS)

### Keyboard Navigation Testing
1. Navigate through judgment panel using `Tab` key
2. Activate roll button with `Enter` or `Space`
3. Expand/collapse completed judgments with keyboard
4. Verify focus indicators are visible
5. Test with `Tab`, `Shift+Tab`, `Enter`, and `Space` keys

### Screen Reader Announcement Testing
1. Start a judgment sequence
2. Verify announcements for:
   - New judgment progression
   - Dice rolling
   - Results and outcomes
3. Check that announcements are clear and contextual
4. Verify timing of announcements (not too fast or slow)

### Focus Management Testing
1. Verify roll button receives focus automatically
2. Check focus doesn't get lost during animations
3. Test focus trap in modal/overlay scenarios
4. Verify focus returns to appropriate element after actions

## Accessibility Features Summary

### ✅ Implemented Features

1. **ARIA Labels**: All interactive elements have descriptive labels
2. **Keyboard Navigation**: Full keyboard support for all interactions
3. **Screen Reader Announcements**: Live regions announce judgment progression and results
4. **Focus Management**: Automatic focus on roll button when it's player's turn
5. **Semantic HTML**: Proper use of headings, buttons, and regions
6. **High Contrast**: Text meets WCAG AA contrast requirements
7. **Touch Targets**: Minimum 44x44px for mobile accessibility
8. **Reduced Motion**: Respects `prefers-reduced-motion` media query
9. **Expandable Sections**: Proper `aria-expanded` and `aria-controls`
10. **Status Updates**: Dynamic content changes announced to screen readers

### 🎯 WCAG 2.1 Compliance

- **Level A**: ✅ All criteria met
- **Level AA**: ✅ All criteria met
- **Level AAA**: Partial (enhanced contrast, extended timeouts)

## Known Limitations

1. **Animations**: Some users may prefer reduced motion - already handled with CSS media query
2. **Timing**: Dice roll animation timing is fixed - could be made configurable
3. **Language**: Currently Korean only - internationalization would require additional work

## Future Enhancements

1. **Configurable Announcements**: Allow users to customize verbosity
2. **Sound Effects**: Optional audio cues for dice rolls and outcomes
3. **High Contrast Mode**: Additional theme for users with low vision
4. **Text-to-Speech**: Optional TTS for narrative content
5. **Keyboard Shortcuts**: Custom shortcuts for power users
6. **Focus Indicators**: Enhanced focus styles with multiple visual cues

## Resources

- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)
- [WebAIM Screen Reader Testing](https://webaim.org/articles/screenreader_testing/)
- [Inclusive Components](https://inclusive-components.design/)
