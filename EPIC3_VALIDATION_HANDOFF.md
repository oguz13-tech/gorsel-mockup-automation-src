# EPIC-3 Local Validation Handoff

Status: **implementation branch only — runtime validation pending**

## 2026-10-13 release-candidate extension

This file originally documented only the feature branch. The validation CLI
now also accepts the more recent safety branch
`safety/epic3-archive-guardrails-20261010`, **but ONLY with an exact
40-character `--expected-head` pin matching the local clean checkout**.
The feature branch keeps backward compatibility and can optionally pin HEAD.

For the safety branch, after reviewing a successful exact-HEAD GitHub CI run,
use a separate clean checkout at that same SHA and add:

```text
--expected-head <full-approved-40-character-git-SHA>
```

Do not use `main`, `epic3-geometry-fix`, arbitrary branches, a short SHA,
or an unreviewed newer commit. Wrong branch/unpinned SHA is rejected before
writing validation output. Validation benchmark/Doctor/preflight evidence
remains distinct from real product visual approval and full normal factory
deployment. Do not weaken/remove Git integrity checks for convenience.

Branch:

`feature/epic-3-geometry-accuracy`

Production safety posture:

- Auto approval remains **OFF**.
- Production rendering consumes only source-hash-matching, active, **APPROVED** template profiles.
- Real golden dataset/images/results must stay outside Git.
- No merge to `main` until local evidence is reviewed.

## One-command evidence bundle

Run from the dedicated clean validation clone on exactly `feature/epic-3-geometry-accuracy`.

Do not rely on the shell's current directory. The previous local worker drifted back to a stale checkout, so every Git check must use `git -C` against the dedicated clone and the validation script must be called by absolute path.

Before running, the following checks must agree and `git status --short` must show no staged/unstaged tracked changes:

```powershell
git -C "C:\AI_WORK\gorsel-mockup-automation-src-epic3-validation" fetch origin
git -C "C:\AI_WORK\gorsel-mockup-automation-src-epic3-validation" checkout feature/epic-3-geometry-accuracy
git -C "C:\AI_WORK\gorsel-mockup-automation-src-epic3-validation" pull --ff-only origin feature/epic-3-geometry-accuracy
git -C "C:\AI_WORK\gorsel-mockup-automation-src-epic3-validation" status --short
git -C "C:\AI_WORK\gorsel-mockup-automation-src-epic3-validation" rev-parse HEAD
git -C "C:\AI_WORK\gorsel-mockup-automation-src-epic3-validation" rev-parse origin/feature/epic-3-geometry-accuracy
```

The two SHA values must be identical. The validation bundle refuses the wrong branch or a dirty tracked worktree and verifies that branch + HEAD remain unchanged through the run.

Keep the real runtime workspace quiescent during validation: do not edit template approvals, source masters, template files, masks, or runtime configuration while the bundle is running. The bundle hashes these read-only runtime inputs before/after preflight and fails integrity if their existence or bytes change.

Source code and mutable production data are intentionally separate:

- clean source checkout: `C:\AI_WORK\gorsel-mockup-automation-src-epic3-validation`
- real runtime workspace: `C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu`
- golden dataset: `C:\AI_WORK\epic2_golden_benchmark`
- evidence output: `C:\AI_WORK\epic3_validation`

Do not copy the runtime DB/templates/golden dataset into the source checkout. The bundle injects the runtime workspace only into factory preflight while keeping the code under test bound to the current Git HEAD.

```powershell
python "C:\AI_WORK\gorsel-mockup-automation-src-epic3-validation\scripts\epic3_validation_bundle.py" --dataset "C:\AI_WORK\epic2_golden_benchmark" --output-dir "C:\AI_WORK\epic3_validation" --runtime-workspace "C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu"
```

The command writes these local-only artifacts:

- `epic3_benchmark.json`
- `geometry_diagnostics.json`
- `scorer_telemetry.json`
- `validation_manifest.json`

The output directory is intentionally required to be **outside the repository**.

## Evidence that must be reported back

Report the exact branch HEAD SHA and literal values from `validation_manifest.json`.

Required checks:

1. All command exit codes, including the mandatory `python_syntax_gate` (`py_compile`) before runtime/data checks.
2. Attempted / valid / excluded golden-sample counts.
3. EPIC-2 vs EPIC-3 global median IoU and Recall@0.50.
4. Per-category EPIC-2 vs EPIC-3 metrics for:
   - 01_Wifi_Kutusu
   - 02_Cam_Tablo_Dikey
   - 02_Cam_Tablo_Yatay
   - 03_Ahsap_Tablo
   - 04_Cam_Dograma
   - 05_Ocak_Arkasi
5. Geometry diagnostic invariants:
   - global classification counts sum to valid_evaluated;
   - every category classification count sum matches its category valid_evaluated.
6. Scorer telemetry sample count and category coverage.
7. Factory preflight result against the explicit real runtime workspace (not the source checkout).
8. Representative real renders from every category, including:
   - text-containing artwork;
   - H and V sources;
   - mixed-orientation cutting-board templates;
   - at least one real occlusion case.
9. Source immutability:
   - golden dataset bytes/hash unchanged;
   - runtime masters/manifest bytes/hash unchanged;
   - approved template source bytes/hash unchanged;
   - original-template backup bytes/hash unchanged;
   - occlusion-mask cache and runtime configuration bytes/hash unchanged during preflight;
   - template-profile SQLite DB bytes/hash unchanged during preflight;
   - legacy `koseler` not overwritten/reordered/rematched.
10. UI/API review flow:
    - analyze remains REVIEW_REQUIRED;
    - manual corner approval persists exact canonical geometry;
    - source hash change makes old approval stale;
    - foreground AI suggestions remain review-only;
    - physical H/V metadata is never inferred from projected quad geometry;
    - fixed-orientation categories use the category physical contract;
    - mixed `04_Cam_Dograma` approval requires an explicit reviewed H/V selection;
    - mixed-category APPROVED profiles without `physical_orientation_verified` evidence are rejected by preflight/render loading and must be re-reviewed;
    - projected orientation is diagnostic only and may differ from physical orientation.

## Release decisions

Do **not** infer autonomous-placement readiness only from detection rate or a single aggregate metric.

A release review must separately decide:

- review-gated production readiness;
- geometry quality by category;
- occlusion rendering quality;
- whether any category still requires manual review;
- whether auto approval remains disabled.

Until a separate explicit release decision is recorded, `TemplateAnalyzer.auto_approval_enabled` must stay false.

## If the bundle fails

Do not patch from memory. Preserve the failing output and report:

- HEAD SHA;
- failing command;
- exit code;
- stdout/stderr;
- affected sample/category where applicable.

Then fix only the demonstrated failure class and rerun the same evidence bundle.
