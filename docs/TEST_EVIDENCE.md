# Executed test evidence — 2026-10-21

## V3 local synthetic suite

- Environment: Linux, Python 3.12.14, OpenCV 5.0.0, NumPy 2.5.4, Pillow 13.0.0, openpyxl 3.1.5.
- Command from checkout root: `python -B -m unittest tests.test_factory_v3 -v`.
- Local execution used the session's installed dependency directory on PYTHONPATH; it is **not** a build/runtime prerequisite. Install requirements in your own environment.
- Result: **22 tests passed, 8.236 seconds**.
- Compile: all **15 Python files under FABRIKA** compiled without executing them before packaging additions. Re-run compile for final checkpoint.
- Coverage: 3/7/13/19 real source slots in synthetic scenes, perspective and two curved openings; mask recall and protected-region leakage; exact preserved pixels; crop geometry and 3 interpolation choices; strong minification; approval and SHA gates; source/mask tampering; same-name different-extension inputs; repeated image/export SHA and mtime preservation; old LOCAL/PDK identity; monotonic numbering; output/export collision; post-publication interruption recovery; cancellation/resume; pause; process lock; recipe invalidation.
- Test source: `tests/test_factory_v3.py`. Raw non-private log: `docs/evidence/factory-v3-local-unittest.txt`.

## Explicitly NOT executed at initial checkpoint

- Native Windows GUI or installer acceptance.
- Actual user PETEK source JPEG mask/render comparison.
- Full V3 six-category end-to-end regression or legacy crash-recovery drill.
- Final candidate build/test from clean checkout (tool is now versioned; validation follows checkpoint).
- New GitHub workflow result (pending push).

## Historical baseline, not V3 evidence

PR #9 Windows 321/321 and Linux PASS were reported earlier. PR #12 Windows/Linux CI passed in the previous work stage. These do not prove V3 acceptance. Recheck GitHub Actions for the exact new head. Never label unexecuted real Windows tests PASS.

## Failures

No failures among the 22 executed V3 tests. Known untested gaps are tracked in WORK_HANDOFF_CURRENT.md and WINDOWS_RELEASE_STATUS.md. Passing synthetic tests does not remove those release gates.

## Post-publication preservation checks

- GitHub implementation checkpoint: `a950a85b055835231fb30750da9f336f250fcc71`, PR #14; exact tree `80572f87a27f04a8cd4741632b2c11f9dfe0e7bb`.
- All 145 tracked Python sources compile; four inherited invalid-escape SyntaxWarnings, zero syntax errors.
- `python scripts/build_windows_factory.py --output <outside-repo>/candidate.zip`: PASS, 245 entries, CRC/hash checks PASS, `tests/test_factory_v3.py` included, no image/DB entries. Build performed at local metadata-equivalent commit `b6fceca3e2491d99d84672ee2db8e99efb9a7498` with the exact same tree.
- Candidate ZIP SHA256: `7926ac59f43bd2e583ddae0fae1fbd91c02fff19d4e6fb59f3aad9d9a45797c8`. Private local build evidence only; not a Windows final delivery.
- PR #13 separate exact-head Windows/Ubuntu CI was verified; URLs and limits are in PARALLEL_IMPLEMENTATION_RECONCILIATION.md.

## First checkpoint CI failure and correction

Initial dedicated CI run https://github.com/oguz13-tech/gorsel-mockup-automation-src/actions/runs/39586751089 failed BEFORE tests because workflow referenced absent `requirements.txt`. Actual root lockfile is `requirements-core.lock.txt`. Corrected the workflow and all new launcher/docs references; no test failures are hidden. Rerun pending for the correction commit. Independent full audit ran its own dependency installation and Ubuntu passed.

The exact preserved source tree's local suite was rerun: 22 tests PASS, 7.366 seconds.

## Corrected exact-head checkpoint CI

At `402fe3e4c5ba2080f6545f7e67f15ef4b3c03141`, https://github.com/oguz13-tech/gorsel-mockup-automation-src/actions/runs/39587055251 completed SUCCESS (Windows and Ubuntu synthetic suite plus compilation). Pinned dependencies installed successfully. The earlier missing-requirements failure is resolved. The separate full-suite rerun 39587055351 was still running at this document update, so no success claim is made for it yet.

PR13 package omission was reproduced locally against exact head `ca6314af44491136373a0c807df732403c37c71b`: test BAT references the test path=True, `git_items()` includes required test=False, core lockfile included=True. No private data used.
