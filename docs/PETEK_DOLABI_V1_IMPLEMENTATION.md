# PETEK DOLABI — 13 Slot Development Candidate

Status: **DRAFT ONLY — NOT INSTALLED — NOT COMMERCIAL QUALITY APPROVED**.

## Purpose
Adds category `06_Petek_Dolabi` without modifying existing six categories' visual-render branch. A reviewed front quad receives opaque, aspect-preserving artwork, then **exactly 13** procedural grey recessed vertical slots with equal planar spacing and symmetric side margins.

The 96 × 86 × 20 cm dimensions are **physical reference metadata**, not an inferred real image measurement; every template needs its own approved geometry.

## Inputs
- A source-approved template front quad (`koseler`) in TL/TR/BR/BL order, and `tip="perspektif"`.
- An opaque BGR artwork image; category orientation is H.
- Optional `petek_slot_spec` dictionary mapped to `SlotSpec` (normalized fractions).
- Optional reviewed `petek_edge_midpoints={"top":[x,y],"bottom":[x,y]}` plus `petek_curve_reviewed=true`. These coordinates are in the **original template image**. The factory scales them together with the scene.

If curved edges are visible but no reliable reviewed midpoints exist, this version does **not** auto-detect them. Do not promote such a template to production.

## Rendering contract
- Existing holes are **not** detected or preserved. They are visually covered by opaque art.
- Artwork is contained with original aspect retained; remaining space is softly filled. No geometric X/Y stretch of the *main design*. Background fill suitability still needs visual review.
- The 13 openings are graphical dark-grey recesses, not physically reconstructed voids. Top/bottom lengths vary mildly and symmetrically.
- Geometry is computed in flat panel coordinates, then projected into scene perspective.
- Invalid geometry blocks output. The original mockup is not modified.
- New render policy is selected by category in `MockupRenderer.process_mockup`; existing category branch remains unchanged.

## User's daily V2 is intentionally NOT changed
`GORSEL_MOCKUP_GUNLUK_KULLANIM_V2.zip` is an independently pinned **nine-template**, five-category runtime controller. It depends on an installed `FILL_V1` / `NUMBER_GUARD_V2` code patch and hash-checked backup; that installed combination is **not identical to the unmodified PR #9 GitHub tree**.

Do not inject PETEK into V2's `BATCH_SELECTION.json` or bypass its hash/approved-profile/backup checks. A separate controlled migration/update after the main PR9+V2 differences are reconciled will be required.

## Missing before safe daily use
1. Integrate new category into any dynamically or statically enumerated UI selectors and onboarding flow, including the installed daily V2 path.
2. Establish and **review** full-front quad, optional curved top/bottom mids, nominal aspect and source SHA for each new template.
3. Calibrate slot widths, margins, curves and shadow realism on varied genuine scenes.
4. Test full factory + V2 version composition and user-visible commercial outputs in isolated Windows environment.
5. Validate SKU/barcode/Excel separately; daily V2 doesn't execute that pipeline.
6. Run full existing regression suites and real Windows acceptance with separate user approval.
7. Do not merge/install based on unit tests alone.

## Tests
`tests/test_petek_dolabi.py` covers 13 components, symmetry, deterministic output, old slit cover in panel interior, both flat and reviewed curved projection, and bad geometry fail-closed.

The output test images provided in the development handoff are **illustrative, not approved sales images**. The sample front edge has visible calibration imperfections.

## Safety
- No existing category renamed; current data/backup/approved corners/SQLite untouched.
- This branch is based on PR #9's fixed commit `37831c73eaf04cc729628ea5cff3ba45bb9d44df`.
- No implicit live installation, PR merge, watcher launch, or DB migration is allowed.
