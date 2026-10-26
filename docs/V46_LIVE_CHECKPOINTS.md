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
