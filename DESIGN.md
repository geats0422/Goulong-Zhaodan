---
name: Neo-Chinese Cyberpunk
colors:
  surface: '#131313'
  surface-dim: '#131313'
  surface-bright: '#3a3939'
  surface-container-lowest: '#0e0e0e'
  surface-container-low: '#1c1b1b'
  surface-container: '#201f1f'
  surface-container-high: '#2a2a2a'
  surface-container-highest: '#353534'
  on-surface: '#e5e2e1'
  on-surface-variant: '#d0c5af'
  inverse-surface: '#e5e2e1'
  inverse-on-surface: '#313030'
  outline: '#99907c'
  outline-variant: '#4d4635'
  surface-tint: '#e9c349'
  primary: '#f2ca50'
  on-primary: '#3c2f00'
  primary-container: '#d4af37'
  on-primary-container: '#554300'
  inverse-primary: '#735c00'
  secondary: '#f1bf4c'
  on-secondary: '#402d00'
  secondary-container: '#b68a17'
  on-secondary-container: '#372700'
  tertiary: '#d0cdcd'
  on-tertiary: '#303030'
  tertiary-container: '#b4b2b2'
  on-tertiary-container: '#454544'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffe088'
  primary-fixed-dim: '#e9c349'
  on-primary-fixed: '#241a00'
  on-primary-fixed-variant: '#574500'
  secondary-fixed: '#ffdf9e'
  secondary-fixed-dim: '#f1bf4c'
  on-secondary-fixed: '#261a00'
  on-secondary-fixed-variant: '#5b4300'
  tertiary-fixed: '#e5e2e1'
  tertiary-fixed-dim: '#c8c6c5'
  on-tertiary-fixed: '#1b1b1c'
  on-tertiary-fixed-variant: '#474746'
  background: '#131313'
  on-background: '#e5e2e1'
  surface-variant: '#353534'
typography:
  display-lg:
    fontFamily: Syne
    fontSize: 64px
    fontWeight: '800'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Syne
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
  headline-lg-mobile:
    fontFamily: Syne
    fontSize: 24px
    fontWeight: '700'
    lineHeight: '1.2'
  body-md:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1.0'
    letterSpacing: 0.1em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 8px
  gutter-desktop: 32px
  margin-desktop: 64px
  gutter-mobile: 16px
  margin-mobile: 20px
---

## Brand & Style
This design system explores the intersection of "Ancient Imperialism" and "Technological Noir." It is a visual philosophy defined by the term **Imperial Circuitry**—where the rigid, structured geometry of traditional Chinese architecture meets the fluid, glowing connectivity of a high-tech future. 

The aesthetic is heavily rooted in **Minimalism** and **High-Contrast**, utilizing vast expanses of "The Void" (Obsidian) to allow "The Light" (Brushed Gold) to feel precious and authoritative. The UI should evoke a sense of high-security, exclusivity, and mystery, as if the user is interacting with a digitized ancient artifact. Visual elements should alternate between sharp, monolithic structures and delicate, glowing linework that mimics both circuit traces and calligraphic strokes.

## Colors
The palette is strictly limited to maintain a high-end, atmospheric tension.
- **Obsidian (#0A0A0A):** The foundation. Use this for the deepest background layers to create a sense of infinite depth.
- **Deep Charcoal (#121212):** Used for "Surface" containers to provide subtle separation from the background without breaking the dark immersion.
- **Brushed Gold (#D4AF37):** The primary action and "power" color. It represents the interface's energy. Use it for critical interactive elements and focal points.
- **Metallic Bronze (#A67C00):** A secondary accent used for state changes (hover/active) and secondary information hierarchies, providing a weathered, antique contrast to the gold.

**Glow Logic:** Gold elements should possess a subtle `0px 0px 12px` outer glow with 30% opacity to simulate a "bloom" effect common in cyberpunk HUDs.

## Typography
The typography strategy contrasts expressive, avant-garde forms with utilitarian precision. 

**Syne** is used for headlines to mimic the bold, rhythmic weight of calligraphic strokes. It should be typeset with tight tracking for a monolithic, architectural look. 

**Hanken Grotesk** provides a clean, modern balance for body copy, ensuring high readability against the dark backgrounds. 

**JetBrains Mono** (monospaced) is used for labels, metadata, and "system status" text, reinforcing the high-tech/cybernetic narrative of the interface. 

All headings should be treated as "artifacts"—give them ample vertical breathing room. Use "Golden Section" ratios for vertical rhythm between text blocks.

## Layout & Spacing
The design system utilizes a **Fixed 12-Column Grid** for desktop, emphasizing symmetry and balance—concepts central to traditional Chinese aesthetics. 

- **Vertical Strips:** Encourage layouts that flow vertically, reminiscent of traditional hanging scrolls. 
- **The Void:** Use aggressive whitespace (margins > 64px) to separate functional modules. Do not fear empty space; it signifies premium quality.
- **Rhythm:** All spacing must be a multiple of the 8px base unit. 
- **Breakpoints:** 
  - Mobile (<768px): 4 columns, 16px gutters.
  - Tablet (768px - 1280px): 8 columns, 24px gutters.
  - Desktop (>1280px): 12 columns, 32px gutters, 1200px max-width container.

## Elevation & Depth
Depth is not communicated through realistic shadows, but through **Luminance and Tonal Layering**.

1. **Base Layer:** Obsidian (#0A0A0A) - The "ground" or the "void."
2. **Elevated Surfaces:** Deep Charcoal (#121212) - These containers should use "ghost borders" (1px solid gold at 10% opacity) rather than shadows.
3. **Interactive Layer:** Elements that sit "above" the UI utilize a 1px solid gold border and a subtle internal gradient from #121212 to #1E1E1E.
4. **The "Pulse":** Critical alerts or active states use a soft, golden bloom (radial-gradient) behind the element to simulate light emanating from the screen.

## Shapes
The shape language is primarily **Sharp (0)** for structural layouts and **Soft (1)** for interactive components. 

Large layout containers, dividers, and images must have 0px corner radii to maintain the "monolithic" and "carved" feel of the system. Buttons and input fields use a minimal 0.25rem (4px) radius to provide a slight tactile affordance, signaling "modern technology" rather than "ancient stone." 

**Decorative Accents:** Use 45-degree clipped corners (chamfers) for button ends or card corners to evoke a futuristic, military-grade hardware aesthetic.

## Components
- **Buttons:** Primary buttons feature a solid Brushed Gold background with Obsidian text. Secondary buttons are "Ghost" style: 1px Gold border, no fill, with Gold text. On hover, they gain a 20% gold fill.
- **Input Fields:** Bottom-border only (2px Bronze). On focus, the border transitions to Gold with a faint 4px glow. Labels are always monospaced and positioned above the input.
- **Cards:** No shadows. 1px Deep Charcoal border. Headers within cards should be separated by a "Golden Thread"—a 1px height line that fades out at the edges using a linear gradient.
- **Chips:** Monospaced text inside a Bronze-outlined pill shape. Used for tags or system statuses.
- **Progress Bars:** Gold "circuitry" lines. The track is Deep Charcoal, and the indicator is a solid Gold bar with a "lead" glow effect.
- **Dividers:** Use ultra-thin (0.5px) lines. Periodically interrupt dividers with small geometric patterns (e.g., three vertical dots or a small square) to mimic decorative joinery.
# Light Theme Extension

Dark remains the primary brand presentation. Light is a high-readability working mode, but it must not become pale cream or low-contrast parchment. The light mode expression is **Bronze Manuscript HUD**: aged bronze paper, ink-black text, darker brushed-gold authority, and restrained cyan-green circuitry for the near-future cyberpunk signal.

Light palette anchors:
- **Bronze Paper (`#B8944D`)**: page background. It should feel like aged silk or oxidized paper, not white.
- **Manuscript Surface (`#D8BF7B`)**: cards, panels, nav, and raised content surfaces.
- **Old Bronze (`#866A2F`)**: raised depth and lower-page gradients.
- **Ink Black (`#151007`)**: primary readable text.
- **Seal Gold (`#2B1A00`)**: primary actions, active states, brand marks, and dividers.
- **Circuit Teal (`#005E66`)**: sparse glow, hover borders, and grid accents to carry the technological/cyberpunk layer.

All page and component colors must use the semantic tokens defined in `frontend/src/style.css`: `--color-bg`, `--color-surface`, `--color-surface-raised`, `--color-border`, `--color-text`, `--color-muted`, `--color-primary`, and `--color-primary-glow`. Light theme components may also use `--color-cyber` and `--color-cyber-glow` as secondary accents. Typography must use `--font-display`, `--font-body`, or `--font-mono`.

# Theme Behavior

`localStorage[goulong-theme-mode]` and `html[data-theme]` are the only theme sources. The stored mode is `dark`, `light`, or `system`; `system` resolves from `prefers-color-scheme` and updates immediately when the OS setting changes. Every page, including authentication and marketing pages, must consume this global state and must not create a separate persisted theme preference.
