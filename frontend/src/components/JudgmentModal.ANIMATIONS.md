# JudgmentModal Animation Implementation

## Overview

This document describes the animation system implemented for the JudgmentModal component, including modal open/close animations, judgment transition animations, GPU acceleration, and accessibility support.

## Implemented Animations

### 1. Modal Opening Animations

**Overlay (Background)**
- Animation: `fadeIn`
- Duration: 0.2s
- Easing: ease-out
- Effect: Fades from transparent to semi-transparent black with blur

**Modal Content**
- Animation: `scaleIn`
- Duration: 0.3s
- Easing: cubic-bezier(0.16, 1, 0.3, 1) - smooth spring-like effect
- Effect: Scales from 95% to 100% while fading in

### 2. Modal Closing Animations

**Overlay (Background)**
- Animation: `fadeOut`
- Duration: 0.2s
- Easing: ease-in
- Effect: Fades from semi-transparent to fully transparent

**Modal Content**
- Animation: `scaleOut`
- Duration: 0.2s
- Easing: cubic-bezier(0.4, 0, 1, 1) - smooth exit curve
- Effect: Scales from 100% to 95% while fading out

### 3. Judgment Transition Animations

**Exit Animation (Current Judgment)**
- Animation: `slideOutLeft`
- Duration: 0.3s
- Easing: cubic-bezier(0.4, 0, 1, 1)
- Effect: Slides left and fades out

**Enter Animation (Next Judgment)**
- Animation: `slideInRight`
- Duration: 0.3s
- Easing: cubic-bezier(0.16, 1, 0.3, 1)
- Effect: Slides in from right and fades in

## Animation State Management

### State Variables

```typescript
const [isClosing, setIsClosing] = useState(false);
const [shouldRender, setShouldRender] = useState(isOpen);
const [judgmentTransition, setJudgmentTransition] = useState<'enter' | 'exit' | null>(null);
const prevJudgmentIndexRef = useRef(currentJudgmentIndex);
```

### Modal Visibility Flow

1. **Opening**: `isOpen` becomes true → `shouldRender` set to true → modal renders with opening animations
2. **Closing**: `isOpen` becomes false → `isClosing` set to true → closing animations play → after 200ms, `shouldRender` set to false → modal unmounts

### Judgment Transition Flow

1. **Detection**: `currentJudgmentIndex` changes
2. **Exit Phase**: Set `judgmentTransition` to 'exit' → play slideOutLeft animation for 300ms
3. **Enter Phase**: Set `judgmentTransition` to 'enter' → update ref → play slideInRight animation for 300ms
4. **Complete**: Set `judgmentTransition` to null

## GPU Acceleration

All animations use GPU-accelerated properties only:
- `transform` (translateX, scale, translateZ)
- `opacity`
- `filter` (backdrop-filter)

Additional optimizations:
- `will-change: transform, opacity` - hints browser to optimize
- `transform: translateZ(0)` - forces GPU layer
- `backface-visibility: hidden` - prevents flickering

## Accessibility: Reduced Motion Support

The implementation respects the `prefers-reduced-motion` media query:

```css
@media (prefers-reduced-motion: reduce) {
  .judgment-modal-overlay,
  .judgment-modal-content,
  .judgment-card-enter,
  .judgment-card-exit {
    animation: none !important;
    transition: none !important;
    will-change: auto;
    transform: none;
  }
}
```

When users have reduced motion enabled:
- All animations are disabled
- Transitions are removed
- GPU hints are cleared
- Transforms are reset

## CSS Classes

### Modal Classes
- `.judgment-modal-overlay` - Base overlay styles
- `.judgment-modal-overlay.closing` - Applied during close animation
- `.judgment-modal-content` - Base modal content styles
- `.judgment-modal-content.closing` - Applied during close animation

### Judgment Transition Classes
- `.judgment-card-enter` - Applied when new judgment enters
- `.judgment-card-exit` - Applied when current judgment exits

## Tailwind Configuration

Custom animations are also defined in `tailwind.config.js`:

```javascript
keyframes: {
  fadeIn: { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
  fadeOut: { '0%': { opacity: '1' }, '100%': { opacity: '0' } },
  scaleIn: { '0%': { opacity: '0', transform: 'scale(0.95)' }, '100%': { opacity: '1', transform: 'scale(1)' } },
  scaleOut: { '0%': { opacity: '1', transform: 'scale(1)' }, '100%': { opacity: '0', transform: 'scale(0.95)' } },
  slideInRight: { '0%': { opacity: '0', transform: 'translateX(20px)' }, '100%': { opacity: '1', transform: 'translateX(0)' } },
  slideOutLeft: { '0%': { opacity: '1', transform: 'translateX(0)' }, '100%': { opacity: '0', transform: 'translateX(-20px)' } },
}
```

## Requirements Validation

### ✅ Requirement 7.1: Modal Opening Animation
- Implemented fadeIn + scaleIn animations
- Smooth spring-like easing curve
- 0.2-0.3s duration for professional feel

### ✅ Requirement 7.2: Judgment Transition Animation
- Implemented slideOutLeft + slideInRight animations
- Sequential exit → enter flow
- 0.3s duration per phase

### ✅ Requirement 7.5: Reduced Motion Support
- Full `prefers-reduced-motion` media query support
- All animations disabled when user prefers reduced motion
- Graceful degradation to instant transitions

### ✅ Requirement 10.2: GPU Acceleration
- Only transform and opacity used
- will-change hints for optimization
- translateZ(0) for GPU layer creation
- backface-visibility: hidden for smoothness

## Performance Considerations

### Animation Timing
- Opening: 300ms total (overlay 200ms, content 300ms)
- Closing: 200ms total (synchronized)
- Judgment transition: 600ms total (300ms exit + 300ms enter)

### Memory Management
- Timers are properly cleaned up in useEffect return functions
- Modal unmounts after closing animation completes
- No memory leaks from animation state

### Browser Compatibility
- CSS animations supported in all modern browsers
- Fallback to instant transitions in older browsers
- GPU acceleration available in Chrome, Firefox, Safari, Edge

## Testing Recommendations

### Manual Testing
1. Open modal → verify smooth fadeIn + scaleIn
2. Close modal → verify smooth fadeOut + scaleOut
3. Navigate between judgments → verify slideOut + slideIn
4. Enable reduced motion in OS → verify animations disabled
5. Test on mobile devices → verify smooth performance

### Automated Testing
- Test animation state transitions
- Verify timer cleanup
- Test reduced motion media query
- Verify GPU-accelerated properties used

## Future Enhancements

Potential improvements for future iterations:
1. Customizable animation speeds (user preference)
2. Alternative animation styles (fade only, slide only)
3. Sound effects synchronized with animations
4. Haptic feedback on mobile devices
5. More sophisticated spring physics
6. Staggered animations for list items

## Related Files

- `frontend/src/components/JudgmentModal.tsx` - Component implementation
- `frontend/src/components/JudgmentModal.css` - Animation styles
- `frontend/tailwind.config.js` - Tailwind animation configuration
- `.kiro/specs/judgment-modal-ui/design.md` - Design specification
- `.kiro/specs/judgment-modal-ui/requirements.md` - Requirements document
