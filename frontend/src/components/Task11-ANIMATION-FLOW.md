# JudgmentModal Animation Flow Diagram

## Modal Opening Animation Flow

```
User Action: Judgment Phase Starts
         ↓
    isOpen = true
         ↓
  shouldRender = true
         ↓
    Modal Renders
         ↓
    ┌─────────────────────────────────┐
    │  Overlay Animation (200ms)      │
    │  fadeIn: opacity 0 → 1          │
    │  backdrop-blur appears          │
    └─────────────────────────────────┘
         ↓
    ┌─────────────────────────────────┐
    │  Content Animation (300ms)      │
    │  scaleIn: scale 0.95 → 1        │
    │  opacity 0 → 1                  │
    │  Spring-like easing             │
    └─────────────────────────────────┘
         ↓
    Modal Fully Visible
    User Can Interact
```

## Modal Closing Animation Flow

```
User Action: All Judgments Complete / Story Starts
         ↓
    isOpen = false
         ↓
   isClosing = true
         ↓
    ┌─────────────────────────────────┐
    │  Overlay Animation (200ms)      │
    │  fadeOut: opacity 1 → 0         │
    │  backdrop-blur fades            │
    └─────────────────────────────────┘
         ↓
    ┌─────────────────────────────────┐
    │  Content Animation (200ms)      │
    │  scaleOut: scale 1 → 0.95       │
    │  opacity 1 → 0                  │
    │  Smooth exit easing             │
    └─────────────────────────────────┘
         ↓
    Wait 200ms (animation complete)
         ↓
  shouldRender = false
         ↓
    Modal Unmounts
    DOM Cleaned Up
```

## Judgment Transition Animation Flow

```
User Action: Next Judgment / Roll Dice Complete
         ↓
currentJudgmentIndex Changes
         ↓
  Detect Index Change
         ↓
judgmentTransition = 'exit'
         ↓
    ┌─────────────────────────────────┐
    │  Exit Animation (300ms)         │
    │  slideOutLeft:                  │
    │  - translateX 0 → -20px         │
    │  - opacity 1 → 0                │
    │  Current judgment slides left   │
    └─────────────────────────────────┘
         ↓
    Wait 300ms
         ↓
judgmentTransition = 'enter'
prevJudgmentIndexRef = currentJudgmentIndex
         ↓
    ┌─────────────────────────────────┐
    │  Enter Animation (300ms)        │
    │  slideInRight:                  │
    │  - translateX 20px → 0          │
    │  - opacity 0 → 1                │
    │  Next judgment slides in        │
    └─────────────────────────────────┘
         ↓
    Wait 300ms
         ↓
judgmentTransition = null
         ↓
    New Judgment Fully Visible
    User Can Interact
```

## State Management Timeline

### Opening Sequence
```
Time    State                           Visual
0ms     isOpen=true                     Nothing visible
        shouldRender=true               
        isClosing=false                 
        
0ms     Render starts                   Overlay starts fading in
                                        Content starts scaling in
        
200ms   Overlay animation complete      Overlay fully visible
        
300ms   Content animation complete      Content fully visible
                                        ✓ Modal ready for interaction
```

### Closing Sequence
```
Time    State                           Visual
0ms     isOpen=false                    Modal fully visible
        isClosing=true                  
        shouldRender=true               
        
0ms     Closing animations start        Overlay starts fading out
                                        Content starts scaling out
        
200ms   Animations complete             Modal invisible
        shouldRender=false              
        isClosing=false                 
        
200ms   Component unmounts              ✓ DOM cleaned up
```

### Judgment Transition Sequence
```
Time    State                           Visual
0ms     Index changes                   Current judgment visible
        judgmentTransition='exit'       
        
0ms     Exit animation starts           Current judgment slides left
                                        and fades out
        
300ms   Exit complete                   Current judgment invisible
        judgmentTransition='enter'      
        prevIndex updated               
        
300ms   Enter animation starts          Next judgment slides in
                                        from right and fades in
        
600ms   Enter complete                  Next judgment fully visible
        judgmentTransition=null         ✓ Ready for interaction
```

## Animation Properties Used

### GPU-Accelerated Properties ✅
```css
/* These trigger GPU acceleration */
transform: translateX()  /* Horizontal movement */
transform: scale()       /* Size changes */
transform: translateZ(0) /* Force GPU layer */
opacity                  /* Transparency */
filter: blur()          /* Backdrop blur */
```

### Non-GPU Properties ❌ (Avoided)
```css
/* These cause layout reflows - NOT USED */
width, height           /* Size changes */
top, left, right, bottom /* Position changes */
margin, padding         /* Spacing changes */
```

## Performance Optimization Flow

```
Animation Triggered
         ↓
    ┌─────────────────────────────────┐
    │  Browser Optimization           │
    │  - will-change hints applied    │
    │  - GPU layer created            │
    │  - Compositor thread activated  │
    └─────────────────────────────────┘
         ↓
    ┌─────────────────────────────────┐
    │  GPU Rendering                  │
    │  - Transform calculations       │
    │  - Opacity blending             │
    │  - No layout reflows            │
    │  - No paint operations          │
    └─────────────────────────────────┘
         ↓
    60 FPS Smooth Animation
         ↓
    Animation Complete
         ↓
    ┌─────────────────────────────────┐
    │  Cleanup                        │
    │  - will-change removed          │
    │  - GPU layer released           │
    │  - Memory freed                 │
    └─────────────────────────────────┘
```

## Reduced Motion Flow

```
User Has Reduced Motion Preference
         ↓
    @media (prefers-reduced-motion: reduce)
         ↓
    ┌─────────────────────────────────┐
    │  Animation Disabled             │
    │  - animation: none !important   │
    │  - transition: none !important  │
    │  - will-change: auto            │
    │  - transform: none              │
    └─────────────────────────────────┘
         ↓
    Instant State Changes
    (No visual animation)
         ↓
    Full Functionality Maintained
    ✓ Accessible Experience
```

## Error Handling Flow

```
Animation State Change
         ↓
    useEffect Triggered
         ↓
    Timer Created
         ↓
    ┌─────────────────────────────────┐
    │  Cleanup Function Registered    │
    │  return () => clearTimeout()    │
    └─────────────────────────────────┘
         ↓
    Component Unmounts OR
    Dependencies Change
         ↓
    Cleanup Function Called
         ↓
    Timer Cleared
         ↓
    ✓ No Memory Leaks
    ✓ No Orphaned Timers
```

## CSS Class Application Flow

### Modal Opening
```
Component Renders
         ↓
isClosing = false
         ↓
Classes Applied:
- judgment-modal-overlay
- animate-fadeIn
- judgment-modal-content  
- animate-scaleIn
         ↓
CSS Animations Play
```

### Modal Closing
```
isOpen becomes false
         ↓
isClosing = true
         ↓
Classes Applied:
- judgment-modal-overlay closing
- judgment-modal-content closing
         ↓
CSS Animations Play
         ↓
After 200ms → Unmount
```

### Judgment Transition
```
Index Changes
         ↓
judgmentTransition = 'exit'
         ↓
Class Applied:
- judgment-card-exit
         ↓
After 300ms
         ↓
judgmentTransition = 'enter'
         ↓
Class Applied:
- judgment-card-enter
         ↓
After 300ms
         ↓
judgmentTransition = null
(No animation class)
```

## Browser Rendering Pipeline

```
JavaScript State Change
         ↓
    React Re-render
         ↓
    Virtual DOM Diff
         ↓
    DOM Update (class change)
         ↓
    ┌─────────────────────────────────┐
    │  Browser Rendering Pipeline     │
    │  1. Style Calculation           │
    │  2. Layout (SKIPPED - no reflow)│
    │  3. Paint (SKIPPED - GPU layer) │
    │  4. Composite (GPU)             │
    └─────────────────────────────────┘
         ↓
    GPU Renders Frame
         ↓
    Display Updated (60 FPS)
```

## Summary

This animation system provides:
- ✅ Smooth 60fps animations
- ✅ GPU-accelerated rendering
- ✅ No layout reflows
- ✅ Proper state management
- ✅ Clean memory management
- ✅ Accessibility support
- ✅ Professional user experience

All animations are carefully orchestrated to provide a polished, performant, and accessible experience.
