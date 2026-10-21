# Architecture decisions — PETEK V3

## ADR-01 — Integration base
Use PR #12 exact commit `7d4d42a6b0ec8015a4080e8e6cdcec71b13cecb8`, which is one commit ahead of PR #9. PR #11 is a sibling branch with overlapping engine/identity edits. Keep it unmerged. Add the new factory alongside existing working engines; no live migration or automatic installation.

## ADR-02 — Remove the 13-hole constraint
The user confirmed 13 was an implementation convenience, not a product specification. Default rendering must retain each source template's actual hole count, widths, positions, bevels, shadows, upper opening and lower floor opening. Procedural V2 remains archival and is never the default V3 path. Product text no longer invents 13 holes or unverified dimensions.

## ADR-03 — Four manual corners + source-bound reviewed mask
The user explicitly accepts manually marking the four front-panel corners, as in other categories. Use TL/TR/BR/BL, show the next point clearly, and require a green-mask preview. Automatic light-wood segmentation proposes the printable area; all non-print pixels use the original source. Profiles bind source SHA256, exact quad, mask SHA256, analyzer and optional physical aspect. Any change requires review. No automatic APPROVED write into the live DB. Masks live in a new local store, never replace existing corner records.

## ADR-04 — Alpha compositing instead of cut/paste files
Composite in the original coordinate system: mask * print + (1-mask) * source. Protected pixels are assigned directly from the source canvas. This avoids re-alignment error and duplicated scene fragments. The mask is binary at storage, with a narrow inward antialias at render time; no outward feather or synthetic hole painting.

## ADR-05 — Fix the actual blur cause
Inspection found unconditional Gaussian-blurred panel background in old `FaceComposer.draw`, then artwork fit over it. That creates the visible blurred side/top bands. New PETEK uses proportional center crop, never stretched fill or blurred padding. The source artwork is warped directly to final output; only strong >2x minification gets an AREA prefilter. Compare LINEAR/CUBIC/LANCZOS on tests; cubic is a balanced initial default, not a universal quality claim. Physical aspect cannot be recovered from four arbitrary image points alone, so optional known aspect is supported and estimates are labeled.

## ADR-06 — Lightweight deterministic CV, not an unvalidated model
Initial choice is OpenCV/NumPy neutral-wood and local-contrast segmentation plus mandatory visual approval/brush correction. No model downloads, GPU runtime, paid service or network required. SAM/matting could improve ambiguous surfaces later, but adding heavy dependencies without real-template benchmark evidence is unjustified. A bright opening can resemble wood; keep this limitation explicit.

Reference consulted: https://docs.opencv.org/4.13.0/da/d54/group__imgproc__transform.html (geometric transforms/interpolation; accessed 2026-10-21). Implementation tests, not documentation alone, determine acceptance.

## ADR-07 — One GUI and shared production management
Seven categories share design selection, queue, progress controls, reports and local Excel/CSV. Existing six-category render path is reused through an adapter with existing source SHA/APPROVED/orientation gates. No core rendering change is silently applied to those categories. All-approved expansion uses existing reviewed backup evidence; it does not auto-approve a directory scan.

## ADR-08 — Identity and durable state
Full input/profile/recipe identity keys distinguish new rendering from old outputs. Never overwrite a different existing output. Product IDs are independent of template/recipe; old default LOCAL/PDK PETEK key formula is retained. A committed AUTOINCREMENT product number is not reused after deletion. Rendering, verification and export are separate states. Local COMPLETED means the local pipeline finished; human visual acceptance remains pending and no marketplace completion is claimed.

## ADR-09 — Privacy and release boundaries
Public GitHub: source, synthetic tests, generalized technical docs and build tools only. Private original images, live JSON/SQLite, reviewed corners, backup inventories, user settings and Windows operational reports remain outside Git. Candidate package comes from a clean commit. No PR merge or live installation during this work.
