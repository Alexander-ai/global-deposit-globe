---
name: globe-viz
description: Build visually striking, intentional 3D globe data visualizations with react-globe.gl / globe.gl / deck.gl. Use this skill whenever the task involves rendering geographic points, arcs, or flows on a 3D globe — mineral deposits, trade flows, seismic events, any lat/lng dataset on a spinning Earth — and especially whenever visual quality, "make it look good," or aesthetic polish is mentioned. Covers the deep-space aesthetic, a materials-derived commodity color system, typography, layout, motion, and globe.gl rendering patterns. Read this before writing any globe rendering or styling code.
---

# Globe Visualization

You are the design lead for a small studio that makes data instruments people remember.
A 3D globe is the easiest thing in the world to make look generic — a blue marble with
scattered dots reads as a stock template. The job here is the opposite: a deliberate,
specific visual identity where the globe is a quiet hero object and the data is the only
thing that glows.

For the full token values (every hex, type scale, spacing, component spec), read
`references/design-system.md`. This file is the direction; that file is the numbers.

## The direction: a deep-space scientific instrument

The Earth hangs in deep space, rendered dark and desaturated so it recedes. The deposit
points are the only saturated color on the screen — a constellation of materials wrapping
the planet. The feeling is a planetarium console or a satellite ground station, not a
consumer travel app. Restraint everywhere except the data.

What this rules out (these are the generic AI-globe defaults — do not ship them):
- A bright photographic "blue marble" Earth texture. Too busy; the points drown in it.
- Rainbow categorical colors assigned in arbitrary order.
- A glowing neon ring / HUD-everywhere sci-fi overlay. One atmosphere halo is enough.
- Pure `#000000` space. Use the near-black desaturated navy from the design system —
  pure black looks like a missing texture, not a choice.

## Color: derive commodity colors from the material

This is the signature move and the thing that makes the palette feel inevitable rather than
arbitrary. Each commodity's point color references the substance itself. Gold is warm
metallic yellow; cobalt is literally cobalt blue; lithium is battery-cell teal; uranium is
the conventional radioactive green; rare earths get an exotic magenta. A viewer half-reads
the colors before they consult the legend. Full hex values are in the design system — use
those exact values, do not invent new ones.

The Earth itself is monochrome (land a hair lighter than ocean, both dark) precisely so
these colors are the only chroma on screen. Never tint the globe surface to compete.

## Typography

Two roles, deliberately paired — not the system default sans for everything:
- **Display / UI** — a grotesque with a little engineered character (the design system names
  the specific face and the Google Fonts import). Used for the title and panel headers.
- **Data / mono** — a monospace for coordinates, counts, and any number. The instrument feel
  lives here: figures in mono read as measured, not decorative.

Sentence case everywhere. No ALL CAPS except, optionally, a single tracked-out eyebrow label.

## Layout

Full-bleed globe as the canvas. Everything else floats over it on translucent, lightly
blurred surfaces so the planet stays the subject:
- A thin top bar: project title (display face) + a one-line dek.
- A docked control panel (left on desktop, bottom sheet on mobile): one toggle per commodity,
  each a color swatch + label + live count in mono. This panel is also the legend — don't
  duplicate a separate legend if the panel already shows the colors.
- A detail card that appears on point-click, dismissable, same translucent surface.
- A bottom-corner attribution line (small, muted) — and it must carry the honest data-vintage
  note. Honesty about the source is part of the craft here.

ASCII sketch (desktop):

```
┌───────────────────────────────────────────────┐
│  ◦ title — one-line dek                         │  ← thin top bar
│ ┌─────────────┐                                 │
│ │ COMMODITIES │            ⊙                     │
│ │ ◗ gold   412│         (the globe,             │
│ │ ◗ copper 388│          full-bleed,            │
│ │ ◗ lithium 96│          dark, points glow)     │
│ │ ◗ cobalt  74│                                 │
│ │   …         │                  ┌────────────┐ │
│ └─────────────┘                  │ deposit card│ │
│                          data: USGS MRDS (…2011)│  ← attribution
└───────────────────────────────────────────────┘
```

## Motion (spend it carefully)

- One orchestrated load moment: globe fades in and begins a slow auto-rotate; let it ease,
  not snap. Stop auto-rotation on first user interaction.
- Hover: a point lifts slightly (small `pointAltitude` bump) and brightens. That's it.
- Filtering: animate point opacity/scale in and out rather than hard-cutting the array.
- Respect `prefers-reduced-motion`: kill auto-rotate and transitions, keep everything usable.
- Resist anything else. Extra motion is the fastest way to make this read as AI-generated.

## react-globe.gl technical patterns

Core setup (React):

```tsx
import Globe from 'react-globe.gl';

<Globe
  globeImageUrl={DARK_EARTH_TEXTURE}   // a dark/desaturated earth, NOT blue-marble
  backgroundColor="rgba(0,0,0,0)"      // let the CSS space background show through
  atmosphereColor={ATMOSPHERE}         // cool blue from the design system
  atmosphereAltitude={0.18}
  pointsData={visiblePoints}
  pointLat="lat"
  pointLng="lng"
  pointColor={(d) => COMMODITY[d.commodity].color}
  pointAltitude={0.01}                 // hover bumps this for the lifted feel
  pointRadius={0.18}
  pointResolution={6}                  // keep low for performance with many points
  onPointClick={setSelected}
/>
```

Rules that keep it fast and clean:
- **Memoize `visiblePoints`** with `useMemo` keyed on the active-commodity set. Never rebuild
  the array inside render or on every frame — that's the main cause of jank.
- For a dark Earth, either use a dark/night texture URL or a flat dark sphere material; the
  design system specifies the approach. Do not use the default day texture.
- Keep `pointResolution` low (5–6). Thousands of high-res spheres will drop frames.
- Atmosphere altitude ~0.15–0.2 gives a believable halo; higher looks like a force field.
- If you outgrow this (full MRDS, or arcs for the supply-chain globe), the same data shape
  ports to deck.gl `GlobeView` + `ScatterplotLayer` / `ArcLayer`. Isolate the globe in one
  component so only it changes.

## Quality floor (build to it without announcing it)

Responsive to mobile (panel becomes a bottom sheet). Visible keyboard focus on every toggle
and the card's close button. `prefers-reduced-motion` honored. Loading and empty states
written plainly in the interface's voice ("No deposits match the current filters." — not a
spinner with no words). Round every number shown to the user.

## Self-check before declaring it done

- Is the globe surface genuinely dark and recessive, with the points as the only saturated color?
- Do the commodity colors map to the materials (per the design system), not an arbitrary order?
- Is there exactly one bold moment (the glowing constellation + halo) and is everything else quiet?
- Is the data vintage stated honestly in the attribution?
- Take a screenshot. Remove one accessory. Does it look like a chosen instrument or a default globe?
