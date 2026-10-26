# V4.6 Live Checkpoints

| Task | Status | Commit | Tests | Notes |
|---|---|---|---|---|
| T00 | DONE | `9f64d24` | Read-only source map and safety preflight recorded | T01 must transfer the isolated chroma engine; no private data staged |
| T01 | DONE | Pending push | Magenta quad detector, review-only API branch, and 3 synthetic tests pass | No automatic approval; non-magenta path remains legacy |

Status meanings: `CODE_DONE`, `TEST_PASS`, `WINDOWS_VERIFIED`,
`HUMAN_ACCEPTED`, and `PRODUCTION_GO` are separate claims. T00 does not claim
Windows verification, human acceptance, or production GO.

## T02.a — selected workspace / child identity (2026-10-26)
CODE_DONE / TEST_PASS: missing persisted workspace stays selected and fails
preflight instead of silently falling back. Editor readiness now checks a random
per-launch token, child PID, code root and runtime root. Running editor prevents
workspace switching. No live data accessed. Tests: `pytest -q
TESTLER/test_v46_workspace_identity.py` = 3 PASS; three changed Python modules
compile. WINDOWS_NOT_VERIFIED. Remaining T02: restore-before-write/startup ingest
gate and native Windows acceptance. Next: T02.b then T03–T10.

## T02.b — restore before watcher/editor writes
Added isolated restore-copy integrity + byte equality check to online SQLite
backup. Startup watcher now requires explicit operator confirmation and a
successful preflight/backup/restore trial before ingest. Editor start also asks
operator consent before backup/open. Test suite: 4 PASS including real disposable
SQLite source invariance and snapshot contents. Compile PASS.
WINDOWS_NOT_VERIFIED; live source inventory and Windows acceptance remain blocked.
T02.a remote checkpoint: da92f0726130271759ab70d4d916312ab0dd2de1.
Next: T03 UI consolidation.

## T03 — review panel simplification
Removed only automatic foreground discovery button/explanation; backend occlusion
safety unchanged. Original/working view buttons are consecutive. Seven report
controls retain handlers in one initially collapsed reports section; destructive
restore stays separate. HTML parser regression: 1 PASS. First invocation without
test dependency path failed (pytest missing); rerun with isolated deps passed.
WINDOWS_NOT_VERIFIED. Next T04 batch chroma dispatch.

## T04.a — batch chroma engine
Batch worker now calls the preserved T01 detector before legacy analysis. Chroma
success writes only source-SHA-bound sidecar draft, never profile/approval;
ambiguous/PETEK magenta abstains without legacy fallback. Existing matched
approvals skip; changed-source approvals block instead of being auto-invalidated.
Fast category button moved immediately below re-detect. Tests: 10 PASS (six
planar worker integrations, PETEK negative, three detector tests). Native Windows,
full job interruption/resume and concurrent edit acceptance remain unverified.
Next T05 canvas angle labels; then T06 ingest/draft acceptance.

## T05 — live canvas edge angles
Canvas draw now paints source-coordinate signed angle deviation beside each
available edge, including just two points. Green <=0.5°, yellow <=2°, red above;
labels say EĞİK (not invalid), are bounded to canvas, and never alter geometry.
Zoom/pan/resize reuse draw transform. Node: 4 PASS (two-point, drag thresholds,
vertical edges, zoom/pan/resize clamping); main.js syntax PASS.
WINDOWS_NOT_VERIFIED; native pointer/visual acceptance pending. Next T06.

## T06.a — fix single-image chroma draft persistence
T01 returned before handling save_as_draft, so bulk selection could display a
successful suggestion that was not saved. Chroma route now persists the same
source-bound review sidecar as legacy, verifies source SHA did not change during
detection, and reports draft_saved accurately. Never calls profile save.
Tests: 8 PASS (batch + request-context single draft integration). Full new-ingest
through human approval and real render remains pending; no live ingest run.
Next T07 render/quality gate review and T08 exports/4K.

## T07.a — approved planar chroma edge treatment
Root cause: alpha feather / rounded corner multiplied source magenta back into
art. For predominantly chroma approved panels, lighting uses neutralized marker
color and marker pixels inside the approved printable mask have full coverage.
Protected pixels remain source-exact. Adjacent marker outside mask rejects with
CHROMA_REVIEW_REQUIRED instead of silently expanding approved geometry. Recipe
bumped so existing outputs/SKUs are not silently reused. Tests: 7 PASS (six
categories white print/outside invariance/1200x1600 plus outside-mask rejection).
This is synthetic evidence only; real source/art A-B and 1→10→100 human quality
GO remain BLOCKED. Not a new approval or universal chroma segmentation guarantee.
Next T08 existing Excel/upscale regressions and release packaging.

## T08 / T09 audit checkpoint
Existing source already fixes non-empty Real-ESRGAN install directory by planning
missing files and rejecting differing collisions; not rewritten. Tightened Python
preflight to reject empty model files. Optional 4K-off path remains independent.
2 targeted tests PASS. Broader existing seven-category cutout/batch/recovery,
Excel HTTPS, naming/restore/upscale regression: 43 PASS / 3 SKIP (15.71s Linux).
No native GPU execution or PowerShell installer execution: WINDOWS_NOT_VERIFIED.
PETEK remains PARTIAL/BLOCKED for real front/slot/curve human acceptance; no fixed
13-slot generation introduced. Existing source-pixel cutout and separate PETEK
Excel code retained. No upload or marketplace call performed.
Next T10 reproducible source-only candidate ZIP and CI artifact.
