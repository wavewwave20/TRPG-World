# JudgmentModal Animation Visual Guide

## Animation Showcase

### 1. Modal Opening Animation

```
Before (t=0ms):
┌─────────────────────────────────────┐
│                                     │
│         [Nothing visible]           │
│                                     │
└─────────────────────────────────────┘

During (t=0-200ms):
┌─────────────────────────────────────┐
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │ ← Overlay fading in
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │   (opacity 0 → 1)
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
└─────────────────────────────────────┘

During (t=0-300ms):
┌─────────────────────────────────────┐
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │ ← Overlay fully visible
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │
│ ▓▓▓▓▓▓▓┌─────────────┐▓▓▓▓▓▓▓▓▓▓▓ │
│ ▓▓▓▓▓▓▓│   Modal     │▓▓▓▓▓▓▓▓▓▓▓ │ ← Content scaling in
│ ▓▓▓▓▓▓▓│   Content   │▓▓▓▓▓▓▓▓▓▓▓ │   (scale 0.95 → 1)
│ ▓▓▓▓▓▓▓│   Growing   │▓▓▓▓▓▓▓▓▓▓▓ │   (opacity 0 → 1)
│ ▓▓▓▓▓▓▓└─────────────┘▓▓▓▓▓▓▓▓▓▓▓ │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │
└─────────────────────────────────────┘

After (t=300ms):
┌─────────────────────────────────────┐
│ ████████████████████████████████████│ ← Overlay fully visible
│ ████████████████████████████████████│
│ ████████┌───────────────┐███████████│
│ ████████│  Judgment 1/3 │███████████│
│ ████████├───────────────┤███████████│
│ ████████│ Character: A  │███████████│ ← Content fully visible
│ ████████│ Action: ...   │███████████│   (scale 1, opacity 1)
│ ████████│ [Roll Dice]   │███████████│
│ ████████└───────────────┘███████████│
│ ████████████████████████████████████│
└─────────────────────────────────────┘
```

### 2. Modal Closing Animation

```
Before (t=0ms):
┌─────────────────────────────────────┐
│ ████████████████████████████████████│
│ ████████┌───────────────┐███████████│
│ ████████│  Judgment 3/3 │███████████│
│ ████████│  [Complete]   │███████████│ ← Modal fully visible
│ ████████└───────────────┘███████████│
│ ████████████████████████████████████│
└─────────────────────────────────────┘

During (t=0-200ms):
┌─────────────────────────────────────┐
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │ ← Overlay fading out
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │   (opacity 1 → 0)
│ ▓▓▓▓▓▓▓┌─────────────┐▓▓▓▓▓▓▓▓▓▓▓ │
│ ▓▓▓▓▓▓▓│   Modal     │▓▓▓▓▓▓▓▓▓▓▓ │ ← Content scaling out
│ ▓▓▓▓▓▓▓│   Content   │▓▓▓▓▓▓▓▓▓▓▓ │   (scale 1 → 0.95)
│ ▓▓▓▓▓▓▓│  Shrinking  │▓▓▓▓▓▓▓▓▓▓▓ │   (opacity 1 → 0)
│ ▓▓▓▓▓▓▓└─────────────┘▓▓▓▓▓▓▓▓▓▓▓ │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │
└─────────────────────────────────────┘

After (t=200ms):
┌─────────────────────────────────────┐
│                                     │
│         [Nothing visible]           │ ← Modal unmounted
│                                     │   DOM cleaned up
└─────────────────────────────────────┘
```

### 3. Judgment Transition Animation

```
Before (t=0ms):
┌─────────────────────────────────────┐
│ ████████████████████████████████████│
│ ████████┌───────────────┐███████████│
│ ████████│  Judgment 1/3 │███████████│
│ ████████├───────────────┤███████████│
│ ████████│ Character: A  │███████████│ ← Current judgment
│ ████████│ Action: ...   │███████████│   visible
│ ████████│ [Next]        │███████████│
│ ████████└───────────────┘███████████│
│ ████████████████████████████████████│
└─────────────────────────────────────┘

Exit Phase (t=0-300ms):
┌─────────────────────────────────────┐
│ ████████████████████████████████████│
│ ████████┌───────────────┐███████████│
│ ████████│  Judgment 1/3 │███████████│
│ ████████├───────────────┤███████████│
│ ███████ │Character: A  │████████████│ ← Sliding left
│ ██████  │Action: ...   │████████████│   (translateX 0 → -20px)
│ █████   │[Next]        │████████████│   (opacity 1 → 0)
│ ████    └───────────────┘████████████│
│ ████████████████████████████████████│
└─────────────────────────────────────┘

Between Phases (t=300ms):
┌─────────────────────────────────────┐
│ ████████████████████████████████████│
│ ████████┌───────────────┐███████████│
│ ████████│  Judgment 2/3 │███████████│
│ ████████├───────────────┤███████████│
│ ████████│               │███████████│ ← Empty space
│ ████████│               │███████████│   (transition moment)
│ ████████│               │███████████│
│ ████████└───────────────┘███████████│
│ ████████████████████████████████████│
└─────────────────────────────────────┘

Enter Phase (t=300-600ms):
┌─────────────────────────────────────┐
│ ████████████████████████████████████│
│ ████████┌───────────────┐███████████│
│ ████████│  Judgment 2/3 │███████████│
│ ████████├───────────────┤███████████│
│ ████████████│Character: B│███████████│ ← Sliding in from right
│ ████████████│Action: ...  │██████████│   (translateX 20px → 0)
│ ████████████│[Roll Dice]  │██████████│   (opacity 0 → 1)
│ ████████████└─────────────┘██████████│
│ ████████████████████████████████████│
└─────────────────────────────────────┘

After (t=600ms):
┌─────────────────────────────────────┐
│ ████████████████████████████████████│
│ ████████┌───────────────┐███████████│
│ ████████│  Judgment 2/3 │███████████│
│ ████████├───────────────┤███████████│
│ ████████│ Character: B  │███████████│ ← New judgment
│ ████████│ Action: ...   │███████████│   fully visible
│ ████████│ [Roll Dice]   │███████████│
│ ████████└───────────────┘███████████│
│ ████████████████████████████████████│
└─────────────────────────────────────┘
```

## Animation Timing Visualization

### Modal Opening Timeline
```
Time:     0ms    100ms   200ms   300ms
          │       │       │       │
Overlay:  ░░░░░░░▓▓▓▓▓▓▓▓████████████
          └─ fadeIn (200ms) ─┘

Content:  ░░░░░░░░░░░░░░░▓▓▓▓▓▓▓▓████
          └──── scaleIn (300ms) ────┘

Result:   [Hidden] → [Appearing] → [Visible]
```

### Modal Closing Timeline
```
Time:     0ms    100ms   200ms
          │       │       │
Overlay:  ████████▓▓▓▓▓▓▓░░░░░░░
          └─ fadeOut (200ms) ─┘

Content:  ████████▓▓▓▓▓▓▓░░░░░░░
          └─ scaleOut (200ms) ─┘

Result:   [Visible] → [Fading] → [Hidden]
```

### Judgment Transition Timeline
```
Time:     0ms    150ms   300ms   450ms   600ms
          │       │       │       │       │
Exit:     ████████▓▓▓▓▓▓▓░░░░░░░
          └─ slideOutLeft (300ms) ─┘

Enter:                    ░░░░░░░▓▓▓▓▓▓▓████
                          └─ slideInRight (300ms) ─┘

Result:   [Old] → [Exiting] → [Empty] → [Entering] → [New]
```

## GPU Acceleration Visualization

### Without GPU Acceleration (❌ Bad)
```
CPU Thread:
┌─────────────────────────────────────┐
│ Calculate → Layout → Paint → Render │ ← All on CPU
│ [Slow, causes jank]                 │
└─────────────────────────────────────┘

Result: 30 FPS or less, janky animation
```

### With GPU Acceleration (✅ Good)
```
Main Thread:
┌─────────────────────────────────────┐
│ Calculate transform/opacity values  │ ← Minimal CPU work
└─────────────────────────────────────┘
                ↓
Compositor Thread (GPU):
┌─────────────────────────────────────┐
│ Apply transforms → Composite layers │ ← GPU handles rendering
│ [Fast, smooth]                      │
└─────────────────────────────────────┘

Result: 60 FPS, smooth animation
```

## Reduced Motion Comparison

### Normal Animation (prefers-reduced-motion: no-preference)
```
Time:     0ms ──────────────────→ 300ms
State:    Hidden → Animating → Visible
Visual:   ░░░░░░ ▓▓▓▓▓▓ ████████

User sees: Smooth fade and scale animation
```

### Reduced Motion (prefers-reduced-motion: reduce)
```
Time:     0ms → 0ms
State:    Hidden → Visible
Visual:   ░░░░░░ → ████████

User sees: Instant appearance (no animation)
```

## Mobile vs Desktop Comparison

### Desktop (max-width: 600px)
```
┌─────────────────────────────────────────────────────┐
│                                                     │
│         ┌─────────────────────────┐                │
│         │  Judgment Modal         │                │
│         │  [600px max width]      │                │
│         │                         │                │
│         │  Centered in viewport   │                │
│         │                         │                │
│         └─────────────────────────┘                │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Mobile (width: 95%)
```
┌───────────────────────────────┐
│ ┌───────────────────────────┐ │
│ │  Judgment Modal           │ │
│ │  [95% of screen width]    │ │
│ │                           │ │
│ │  Fills most of screen     │ │
│ │                           │ │
│ │  Small margins on sides   │ │
│ │                           │ │
│ └───────────────────────────┘ │
└───────────────────────────────┘
```

## Animation Easing Curves

### Opening (cubic-bezier(0.16, 1, 0.3, 1))
```
Progress
  1.0 │                    ╱─────
      │                  ╱
      │                ╱
  0.5 │              ╱
      │            ╱
      │          ╱
  0.0 │────────╱
      └─────────────────────────→ Time
      0ms                    300ms

Effect: Spring-like, overshoots slightly, feels bouncy
```

### Closing (cubic-bezier(0.4, 0, 1, 1))
```
Progress
  1.0 │─────╲
      │      ╲
      │       ╲
  0.5 │        ╲
      │         ╲
      │          ╲
  0.0 │           ╲────────
      └─────────────────────────→ Time
      0ms                    200ms

Effect: Smooth deceleration, feels natural
```

## Summary

The animation system provides:
- ✅ Professional, polished appearance
- ✅ Smooth 60fps performance
- ✅ GPU-accelerated rendering
- ✅ Accessible (reduced motion support)
- ✅ Responsive (mobile and desktop)
- ✅ Well-timed transitions
- ✅ Natural easing curves

All animations are carefully designed to enhance the user experience without being distracting or causing performance issues.
