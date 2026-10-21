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
