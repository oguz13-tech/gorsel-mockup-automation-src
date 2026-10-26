# Resume from PR #52 / Issue #56

1. Fetch the latest feature/v46-safe-consolidation-20261024; read Issue #56 newest
   checkpoint and docs/V46_ACCEPTANCE_CURRENT.md. Do not rebuild T00/T01.
2. Inspect V4.6 Windows candidate package workflow results; fix failed jobs before
   treating Actions artifact as tested. Native GUI remains WINDOWS_NOT_VERIFIED.
3. Complete T04 remaining persistent-job stop/resume/concurrent edit tests and
   T06 real new-ingest → DRAFT → explicit human approval → render acceptance.
4. T07: real artwork/source/approved mask A-B on new images, not accepted 346
   preview gallery; verify magenta boundary/mask containment, no false success.
5. T08: Windows optional GPU smoke/installer, offline output + real HTTPS Excel;
   no automatic cloud upload. T09: actual human PETEK front/vents/curve mask and
   separate export acceptance; do not fabricate fixed slots or claim 7/7 final.
6. Only after real Windows acceptance may the candidate become WINDOWS_VERIFIED.
   Keep PR draft/unmerged. Each small change test + commit + remote checkpoint.

Reproduce isolated tests using MERKEZ/requirements-v46-lock.txt, pytest
TESTLER/test_v46_*.py and the exact workflow suite; build with
python scripts/build_v46_candidate.py --output <new-empty-directory>.
Source code and runtime remain separate; no live or original data in ZIP.
