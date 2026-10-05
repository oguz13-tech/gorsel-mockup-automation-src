# EPIC-3 Local Validation Handoff

Status: **implementation branch only — runtime validation pending**

Branch:

`feature/epic-3-geometry-accuracy`

Production safety posture:

- Auto approval remains **OFF**.
- Production rendering consumes only source-hash-matching, active, **APPROVED** template profiles.
- Real golden dataset/images/results must stay outside Git.
- No merge to `main` until local evidence is reviewed.

## One-command evidence bundle

Run from the clean source workspace:

```powershell
python scripts/epic3_validation_bundle.py --dataset C:\AI_WORK\epic2_golden_benchmark --output-dir C:\AI_WORK\epic3_validation
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

1. All command exit codes.
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
7. Factory preflight result.
8. Representative real renders from every category, including:
   - text-containing artwork;
   - H and V sources;
   - mixed-orientation cutting-board templates;
   - at least one real occlusion case.
9. Source immutability:
   - original artwork bytes/hash unchanged;
   - approved template source bytes/hash unchanged;
   - legacy `koseler` not overwritten/reordered/rematched.
10. UI/API review flow:
    - analyze remains REVIEW_REQUIRED;
    - manual corner approval persists exact canonical geometry;
    - source hash change makes old approval stale;
    - foreground AI suggestions remain review-only.

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
