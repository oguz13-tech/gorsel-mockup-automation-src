# Reproduce local Phase 3

This lab is intentionally separate from V4.6 and contains no production database,
approved geometry, customer files, or model cache in a public delivery.

## Existing-evidence evaluation

From the isolated reference lab, with `PHASE3_GEOMETRY_ROOT` pointing to the
separate read-only geometry fixture root:

```powershell
python run_phase3_ab_experiment.py
python create_phase3_public_reports.py
python build_phase3_visual_review.py
```

The first command reads the existing anonymized detector, registration, and SAM
reports. It does not download weights or run model inference again. It must report
170 input rows, seven categories, `UNKNOWN_GT`, and `NO_GO_REVIEW_REQUIRED`.

## Synthetic fixture smoke test

The public repository cannot run the 170 private/local images. A future public CI
test should provide synthetic images and JSON rows with the same schema, then
assert:

- malformed boxes are rejected;
- detector consensus is only a draft;
- missing approved ground truth produces `UNKNOWN_GT`;
- center-point masks never become approved geometry;
- no source path, SQLite path, or private image is copied into reports.

## Acceptance boundary

The local gallery is evidence for human review, not a production approval. A
category-specific printable surface, PETEK contour/slot, or four-corner profile
requires approved source-SHA identity or explicit human review.
