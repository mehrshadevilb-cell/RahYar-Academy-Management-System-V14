# Skill: Web UI Design (ArtistYar / modern minimal)

## Goal
Ship calm, premium, RTL-first interfaces. Prefer fewer elements with stronger hierarchy over dense dashboards.

## Visual system (locked)
- Background: near-black ink (`#0c0c0b`)
- Text: warm sand (`#f5efe3`)
- Accent: restrained gold (`#c9a227`) — use sparingly (CTA, focus, key numbers)
- Borders: white at 6–10% opacity, never harsh pure white lines
- Radius: large (2xl/3xl) for cards; full for primary buttons
- Type: Vazirmatn (or equivalent Persian), generous line-height (1.7–1.9 on body)

## Layout rules
1. Max content width ~72rem; center with horizontal padding 1.25–2rem.
2. Section rhythm: large vertical gaps (py-16+) — whitespace is a feature.
3. One primary CTA per view; secondary actions are ghost/outline.
4. Cards: subtle border + soft shadow; hover = border gold/25 and slight lift, not loud animation.
5. Grids: 1 → 2 → 3 columns; never force 4 columns on marketing pages.

## Components
- Header sticky, blurred, thin bottom border
- Inputs: rounded-2xl, quiet border, gold focus ring
- Tables: minimal header, no zebra noise, status as text not badges spam
- Empty states: one sentence + one action
- Errors: short Persian, actionable, never stack traces

## RTL
- `dir="rtl"` on html; logical properties preferred
- Icons that imply direction must flip or use neutral marks
- Numbers/prices remain readable (fa-IR locale when showing toman)

## Accessibility
- Focus visible rings on interactive elements
- Contrast: sand on ink for body; gold only for emphasis, not long paragraphs
- Touch targets ≥ 40px on mobile

## Anti-patterns
- Neon gradients, glassmorphism overload, particle backgrounds
- Multiple competing primary buttons
- Tiny gray text on dark gray
- Decorative illustration that competes with content
- English-only microcopy on Persian-first surfaces

## When editing ArtistYar-Website
Keep `tailwind` tokens (`ink`, `sand`, `gold`, `card-ay`, `btn-primary`, `btn-ghost`, `input-ay`). Extend tokens instead of inventing one-off colors.
