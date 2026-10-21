# Current checkpoint — 2026-10-21

Master: issue #24. Branch: fix/final-15-package-tests-20261021.
Base PR13 ca6314af44491136373a0c807df732403c37c71b. Resolve latest checkpoint SHA with git rev-parse HEAD.

## Completed in this checkpoint
Reproduced missing tests/test_petek_v3.py in PR13 release enumeration.
Explicitly allowlisted and required that synthetic test plus dependency files.
Windows launch/test scripts use a package-local Python 3.11 venv, pinned test dependencies, and preserve test exit status.
CI builds on Windows and Ubuntu and runs tests from extracted ZIP outside checkout, with checkout PYTHONPATH removed.
No merge, installation, data migration or private file publication.

## Source reconciliation
| Source | Verified state | Integration status |
|---|---|---|
| PR13 ca6314af | Flask PETEK, source-preserving mask, batch, release | Base; packaging fixed here |
| PR14 b936a6b8 | Independent Tk/queue preservation, 22-test suite | Retained separately; no wholesale merge |
| Private V3.7 | PR13 comments describe Tk curves/viewport/registry and 48 reported tests | Bytes not yet inspected in this checkpoint; do not claim integration |
| Old daily center | Six categories / ten-template workflow described in prior evidence | No files changed in this patch |

## Remaining
#15 remains partial: inspect private V3.7 source, verify manifest, sanitize and checkpoint source; choose canonical UI after source comparison.
#18 next: artifact identity must bind quad and physical aspect; review mask-store compatibility before changing identity. Then #16, #17, #19, #20, #21, #22, #23.
Native Windows GUI, seven-category golden set, real masking QA, crash recovery and final installation/rollback are NOT accepted.
