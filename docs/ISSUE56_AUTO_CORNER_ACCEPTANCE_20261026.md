# Issue #56 Automatic-Corner Acceptance

This public-safe summary records the isolated acceptance run. Private source
images, SQLite files, customer assets, and local Windows paths are deliberately
excluded.

## Result

**Automatic four-corner decision: KISMEN (PARTIAL).**

| Category group | Tested | Automatic geometry pass | Review required |
|---|---:|---:|---:|
| Six available planar categories | 6 | 3 | 3 |
| PETEK | 0 | 0 | Blocked |

The detector ran without using registered APPROVED quadrilaterals as input.
Registered geometry was used only after detection for objective evaluation.
Three categories met the isolated IoU and normalized corner-error thresholds;
three produced a candidate requiring human review.

## Safety and negative acceptance

- New/unapproved input: zero output.
- Synthetic SHA mismatch: zero output.
- PETEK without an approved physical front-mask: zero output.
- Automatic detections were not written to the database.
- No source SHA was promoted to `APPROVED`.
- Existing APPROVED geometry, source assets, databases, and historical outputs
  remained unchanged.

## Mockup evidence

Six derived 3:4 mockups were generated in the isolated review workspace.
Pixels outside the selected quadrilateral remained unchanged in the measured
checks. Magenta residue and optical effects are not declared production-pass:
some magenta residue remained and reflection/rodaj/occluder quality still
requires human visual acceptance.

## Verification

- Isolated SQLite integrity check: PASS.
- Duplicate active template UID check: PASS (0 duplicates).
- Automatic-corner cases: 6.
- Negative cases with output: 0.
- PETEK outputs: 0.

This result is evidence for PR #52 / Issue #56 review only. It is not a
production GO or automatic approval of any template.
