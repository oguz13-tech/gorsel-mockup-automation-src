# PETEK V3 QA evidence

At coding stage: tests have been authored but do NOT count as passed until run.
Primary suite: tests/test_petek_v3.py (synthetic photos / source masks / QA / batch / API).
Legacy tests: tests/test_number_guard_v2.py; tests/test_fill_v1_delivery.py and full repository suite.

Final planned commands:
python -m pip install -r requirements-petek-v3.txt
python -m compileall -q SABLON_V2_MIMARI/core scripts/petek_v3_windows_launcher.py scripts/petek_v3_windows_release.py
python -m pytest -q tests/test_petek_v3.py
python -m pytest -q tests/test_number_guard_v2.py tests/test_fill_v1_delivery.py
python scripts/petek_v3_windows_release.py build --destination dist
python scripts/petek_v3_windows_release.py inspect <zip>

Record OS, commit SHA, actual counts/failures, CI URLs and screenshots AFTER execution. Passing synthetic pixel checks is not the same as approved real mockup appearance or safe Windows live installation.

## Issue #15 packaging checkpoint, 2026-10-21
Executed Linux Python 3.12 with preinstalled integration-deps:
- Before fix: git_items excluded tests/test_petek_v3.py (False).
- python -m pytest -q tests/test_petek_v3.py: 19 passed (1.43 s).
- Clean committed candidate build and manifest inspection: 113 files, OK.
- Extracted candidate into independent temporary folder; ran python -m pytest -q tests/test_petek_v3.py there: 19 passed. PYTHONPATH supplied only external installed dependencies, not checkout source.
- git diff --check: PASS.
Windows BAT execution and native GUI NOT run locally. Added Windows/Ubuntu CI extracted-package test; result pending.

## Sprint2 Milestone A
Linux Python3.12, external integration-deps. Before fix: pytest -q tests/test_petek_v3.py -k physical_aspect FAILED: distinct output SHAs but identical artifact key. After fix: pytest -q tests/test_petek_v3.py: 22 PASS (including geometry, ratio, recipe, art, marketplace, numeric canonicalization, no-overwrite and existing batch reuse). New CI/native Windows not claimed.

Sprint2 B partial: missing-receipt test PASS; concurrent reservation test initially FAIL because nonexistent output accepted as rendered. Fixed transaction-level file/SHA check; full `python -m pytest -q tests/test_petek_v3.py`: 24 PASS on Linux. No native Windows/process-kill claim.

## Brush hotfix
Node24.19: node --test tests/js/petek_brush.test.cjs: 3 PASS (solid continuous sweep, quad clip with outside center, cursor scaling). node --check static JS PASS. These are helper tests, not native Windows GUI or real-photo visual acceptance.
