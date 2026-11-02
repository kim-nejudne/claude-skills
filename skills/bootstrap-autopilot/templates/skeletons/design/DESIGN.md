# <App> design reference

Build sessions follow this from F01. The mock files in this folder are the visual target; the spec and this file win where they disagree with a mock. Anything not covered here follows the nearest existing component, and a gap is recorded in `docs/DECISIONS.md`.

Source: <list each mock file in docs/design/ and where it came from (claude.ai artifact URL, the spec's text)>.

## Tokens

| Token | Value | Use |
| --- | --- | --- |
| `bg` | `#…` | page background |
| `surface` | `#…` | cards, panels |
| `text` | `#…` | primary text (≥ 4.5:1 on `bg` and `surface`) |
| `muted` | `#…` | secondary text (≥ 4.5:1) |
| `accent` | `#…` | primary actions, focus ring |
| `danger` | `#…` | destructive actions, errors |

Spacing scale: <e.g. 4, 8, 12, 16, 24, 32, 48>. Radius: <values>. Shadows: <values or none>. Light/dark: <one theme or both; how dark is derived>.

Components use only these tokens: no literal colours, sizes or shadows outside them.

## Type

| Role | Face | Weight | Size / line height |
| --- | --- | --- | --- |
| Display | … | … | … |
| Body | … | … | … |
| Numbers / code | … | … | … |

Font loading: <self-hosted woff2 or Google Fonts, subsets, `font-display`>. No other faces or weights.

## Components

For each: anatomy, states (default, hover, focus, active, disabled, loading, error), sizes, and which mock shows it.

- **Button** — …
- **Input** — …
- <…>

## Screens

One section per screen in the spec, in flow order.

### <Screen name>

- Mock: `docs/design/<file>.html` (<which part>)
- Layout: <structure at each target size>
- Content and hierarchy: <what is largest, what is secondary>
- States: empty, loading, error, <app-specific>
- Spec vs mock: <any difference and which wins>

## Targets

Viewports: <e.g. 360×640, 390×844, 1280×800, 1920×1080>. Browsers: <e.g. Safari iOS 16.4+, Chrome Android 10+, desktop evergreen>. Motion: <durations, easing; `prefers-reduced-motion` behaviour>.

## Definition of done for UI

- Matches the mock's structure and hierarchy at every target viewport, with no horizontal scroll.
- Only tokens from this file; contrast ≥ 4.5:1 for text.
- Every interactive element has visible focus and a ≥ 44×44 px target on touch.
- Empty, loading and error states exist.
