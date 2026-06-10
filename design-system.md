# Design system — deposit globe

Concrete token values for the `globe-viz` skill. Mirror the relevant ones into
`src/styles/tokens.css` as CSS custom properties. These are the law; if a value isn't here,
don't introduce it without a reason.

## Palette

### Environment (the dark, recessive stage)

| Token | Hex / value | Use |
|---|---|---|
| `--space` | `#080B14` | Page / space background (near-black desaturated navy, NOT pure black) |
| `--space-2` | `#0C1120` | Subtle vignette toward edges, optional |
| `--ocean` | `#10182B` | Globe ocean base |
| `--land` | `#1B2540` | Globe landmasses (just lighter than ocean) |
| `--atmosphere` | `#4DA6FF` | Atmosphere halo (cool blue) — the only ambient glow |
| `--ui-surface` | `rgba(12,17,32,0.72)` | Translucent panels/cards, with `backdrop-filter: blur(10px)` |
| `--hairline` | `rgba(255,255,255,0.08)` | Borders, dividers (single-pixel) |
| `--text` | `#E8ECF4` | Primary text |
| `--text-muted` | `#8A93A8` | Secondary text, attribution, counts label |
| `--focus` | `#7FC0FF` | Keyboard focus ring |

### Commodity colors (derived from the materials — use these exact values)

| Commodity | Hex | Rationale |
|---|---|---|
| Gold | `#F2C14E` | Warm metallic yellow |
| Copper | `#C66B3D` | Oxidized copper / penny |
| Lithium | `#4FD1C5` | Battery-cell teal |
| Cobalt | `#2D6BE0` | Literally cobalt blue |
| Nickel | `#9FB4A7` | Pale metallic green |
| Rare earths (REE) | `#B86BD6` | Exotic magenta — the "strategic" elements |
| Zinc | `#7A8AA0` | Blue-gray galvanized metal |
| Uranium | `#8FE34D` | Conventional radioactive green |
| Silver | `#D6DCE6` | Cool light metallic |
| Other / unclassified | `#5A6478` | Muted neutral, recedes behind the named commodities |

Point glow: render points at full color; on hover, lighten ~12% and bump altitude.
Inactive (filtered-out) commodities are removed from the data, not greyed in place.

## Typography

Google Fonts import:

```html
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
```

| Role | Family | Use |
|---|---|---|
| Display / UI | `'Space Grotesk', sans-serif` | Title, panel headers, labels — engineered, a little characterful |
| Data / mono | `'IBM Plex Mono', monospace` | All numbers: counts, coordinates, the instrument feel |

Type scale (rem): title 1.5 / dek 0.95 / panel header 0.8 (tracked +0.04em) / label 0.9 /
count 0.85 (mono) / attribution 0.75 (muted). Weights: 400 body, 500 emphasis, 600 title.
Sentence case throughout.

## Spacing & shape

- Spacing steps: 4, 8, 12, 16, 24, 32 px.
- Panel/card radius: 12px. Toggle/swatch radius: 6px. Globe has no chrome.
- Panel padding: 16px. Gap between toggles: 4px.
- Single-pixel `--hairline` borders only; no drop shadows except a soft one under floating
  panels for legibility against the globe: `0 8px 32px rgba(0,0,0,0.4)`.

## Components

**Control panel (also the legend)** — translucent `--ui-surface`, blurred, docked top-left
with ~24px inset. Header "Commodities" (display, tracked). Each row is a button: a 12px
color swatch (commodity color), label (display), and right-aligned count (mono, `--text-muted`).
Active rows full-opacity; inactive rows at ~0.45 opacity with the swatch hollow. Whole row is
the toggle; visible focus ring (`--focus`).

**Deposit detail card** — same surface, appears bottom-right on point click. Deposit name
(display, 500). Then mono rows: commodity (with swatch), deposit type, `lat, lng` to 4 dp.
A close button (×) with `aria-label="Close"` and focus ring. Dismiss on Escape too.

**Attribution** — bottom-center or bottom-left, `--text-muted`, 0.75rem, mono. Must read:
`Data: USGS MRDS (global, not updated since 2011) + Critical Minerals in Ores · locations historical & approximate`.

## Signature element

The constellation: thousands of material-colored points wrapping a dark planet under a thin
blue atmosphere, with a slow load-in rotation. That is the one bold thing. Keep the panel,
type, and motion disciplined so it stays the hero.

## Globe surface approach

Prefer a flat dark sphere over a photographic texture: a `MeshPhongMaterial`-style dark
ocean (`--ocean`) with landmasses in `--land`, no clouds, no specular sea. If using a
texture URL, pick a dark/desaturated land-only or night earth — never the default day
"blue marble." The test: the globe should look like slate, and the only color on screen
should be the deposits.

## CSS tokens starter (`src/styles/tokens.css`)

```css
:root {
  --space: #080B14;
  --ocean: #10182B;
  --land: #1B2540;
  --atmosphere: #4DA6FF;
  --ui-surface: rgba(12,17,32,0.72);
  --hairline: rgba(255,255,255,0.08);
  --text: #E8ECF4;
  --text-muted: #8A93A8;
  --focus: #7FC0FF;

  --c-gold: #F2C14E;
  --c-copper: #C66B3D;
  --c-lithium: #4FD1C5;
  --c-cobalt: #2D6BE0;
  --c-nickel: #9FB4A7;
  --c-ree: #B86BD6;
  --c-zinc: #7A8AA0;
  --c-uranium: #8FE34D;
  --c-silver: #D6DCE6;
  --c-other: #5A6478;

  --font-display: 'Space Grotesk', sans-serif;
  --font-mono: 'IBM Plex Mono', monospace;
  --radius-card: 12px;
  --radius-swatch: 6px;
}
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
```
