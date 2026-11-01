# Seven-category photometric white recovery – 1 Nov 2026

Based on the previous **SEVEN_CATEGORY_PHOTO_DAYLIGHT_V1_20261101** Windows ZIP.

## Changes

- The neutral print-white center target grows from `scene_white + .115` to
  `scene_white + .145`, capped at `.982`. The left edge stays anchored to
  the real photographed painted cabinet and the ramp remains smooth.
- Neutral white-only recovery after two-band sun attenuation: natural
  max `.012`, strong max `.028` normalized RGB. No saturation shift, no
  reclassification of protected source pixels or physical black vents.
- Strong matte grain glints capped at `.988` only where the neutral-white
  mask is active, keeping diffuse highlight below pure display-white.
- New sunlight recipe V2 and selected-store `_W2` filename suffix keep
  new opt-in outputs distinct from old V1 outputs.
- PINK MARKER REPAIR, source fringe, slot geometry, wall shadow and PETEK
  print pipeline source files are BYTE-FOR-BYTE unchanged from previous ZIP.

## Acceptance

The code was tested with synthetic scene masks and photometric tone checks.
Real Windows user scenes are still **WINDOWS_NOT_VERIFIED**.
