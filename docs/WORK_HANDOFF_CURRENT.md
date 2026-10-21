# Current engineering handoff — 2026-10-21

## Status: ARCHIVAL PARALLEL CHECKPOINT — NOT THE ACTIVE RELEASE LINE

**Reconciliation update:** while this work was paused, PR #13 advanced independently.
The active integration candidate is branch `feature/petek-v3-source-preserving-factory-20261021`,
head `ca6314af44491136373a0c807df732403c37c71b`, [PR #13](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/13).
This branch preserves Astra's previously local implementation without overwriting PR #13.
Do NOT merge both implementations wholesale or give the user two competing final applications.
Read `docs/PARALLEL_IMPLEMENTATION_RECONCILIATION.md` first.

Goal: one local Windows factory for seven categories, source-detail-preserving PETEK V3, durable jobs, immutable outputs and local product spreadsheets. No marketplace publishing. Preserve live templates, approved corners, JSON, SQLite and all original backups.

- Active branch: `checkpoint/astra-petek-v3-local-20261021`
- Integration parent: `7d4d42a6b0ec8015a4080e8e6cdcec71b13cecb8` (PR #12)
- Latest published implementation checkpoint SHA: `a950a85b055835231fb30750da9f336f250fcc71`. Later docs-only updates are identified by the branch HEAD (`git rev-parse HEAD`); a commit cannot contain its own SHA.
- Draft preservation PR: [#14](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/14). Active integrated candidate remains PR #13.
- Writer policy: one agent owns this branch. Fetch and compare HEAD before writing; use a separate branch if it moved. Never force-push or merge without explicit approval.

## Verified PR topology

| PR | Head | Role |
|---|---|---|
| [#9](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/9) | `37831c73eaf04cc729628ea5cff3ba45bb9d44df` | Audited historical release base |
| [#11](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/11) | `49a169806c84686db789f5906563d87006caf5a8` | Independent procedural 13-slot experiment; not merged |
| [#12](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/12) | `7d4d42a6b0ec8015a4080e8e6cdcec71b13cecb8` | One commit ahead of #9; NumberGuard + proportional fill |

All three were read from GitHub during this session: open, draft, unmerged. PR #11 modifies `pc_master_factory.py` and `template_identity.py`, overlapping #12. V3 therefore starts additively from #12, not a blind merge of #11. No original core file was modified in this checkpoint.

## Implemented code (not just design)

- `FABRIKA/petek_v3.py`: four-corner validation, proposed source-specific wood mask, explicit reviewed profile, SHA binding, immutable masks, proportional crop, one perspective warp, conditional minification prefilter, exact protected-pixel compositing.
- `FABRIKA/review.py`: four ordered manual corner clicks, green mask preview, optional correction brush/undo, artwork preview, explicit human mask approval. Curved openings are masks, not synthetic geometry.
- `FABRIKA/app.py`: single seven-category GUI, source/config selectors, PETEK profile list, launch/pause/resume/cancel and output reports.
- `FABRIKA/production.py`: shared durable batch orchestration; existing six-category adapter; input snapshots, individual failures, local output reports/ZIP; network disabled in worker.
- `FABRIKA/queue_store.py`: persistent jobs/events, stable product IDs, monotonically increasing product numbers, LOCAL/PDK compatibility with old PETEK IDs, immutable verified CSV/XLSX, explicit state transitions.
- `FABRIKA/safety.py`: exclusive publication, digest checks, kernel-released process lock.
- `FABRIKA/legacy/`: preserved daily render adapter and approval gates; generic configurable runtime/backup paths. Optional discovery now supports all qualifying approved profiles instead of an arbitrary per-category cap.
- `FABRIKA/legacy_petek.py`: archived procedural engine; not default V3 route.
- `archive/merkez_v2/`: sanitized previously delivered center/commerce code, for continuity only.
- `scripts/build_windows_factory.py`: clean-checkout deterministic source-only candidate ZIP builder; excludes live JSON, DB, photos and private settings.
- Windows launch/test BAT/PowerShell and CI workflow.
- `tests/test_factory_v3.py`: 22 executed tests, all passed on local Linux (see TEST_EVIDENCE).

## Unfinished / known risks — do not hide

1. Real source templates were just supplied privately; no actual V3 render or mask evaluation has yet been performed on them. The previously supplied PETEK results exhibit blurred fill and artificial slots. Original JPEGs must never be published.
2. Native Windows GUI, clean dependency installation, candidate package acceptance and rollback drill are pending.
3. Full existing six-category regression suite has not yet been rerun at this V3 checkpoint. Legacy adapter all-approved selection and real Windows source verification need end-to-end coverage.
4. Legacy daily per-job `JOB.lock` and global `RUNNING.lock` still use old exclusive files. A crash can leave these requiring explicit checked recovery. New V3 PETEK locks recover via OS locks. Do not advertise unattended recovery for the legacy path yet.
5. Mask analysis assumes light/neutral wood. Light backgrounds through holes may be ambiguous. Human green-mask approval is mandatory; brush fallback exists. No segmentation confidence score is a substitute for approval.
6. Source preservation is exact relative to the once-formatted 1200x1600 source canvas. If original dimensions differ, resampling changes source pixels; do not claim byte equality to the original JPEG.
7. Four corners determine projected geometry, not physical aspect uniquely. Optional physical en/boy ratio is available; otherwise report marks estimated aspect.
8. `legacy_store` and profile destination paths need an additional adversarial overlap review before release. Review UI must guard against accidental writes into protected roots. Parent V3 worker currently has network denial; the old worker has stronger write-boundary auditing.
9. Old PETEK SKU compatibility covers default LOCAL/PDK only. Custom prefixes/store groups require a read-only reconciliation. No old commerce DB migrated.
10. Common queue final verification/export is tested; full process-kill injection and full Windows UI behavior are not. Failures leave durable receipts, but production readiness is withheld.
11. Current launcher probes available dependencies; exact version enforcement, offline wheels/clean bootstrap and final installer/backup tooling are not finished. A reproducible candidate builder is present, not a proven final installer.
12. A source can change between display/validation and profile save; editor checks SHA before save, but a further full snapshot/TOCTOU review is required.

## Next exact step

First verify PR #13 and this separate preservation checkpoint. Compare implementations before selective porting; continue the integrated release on a fresh branch from PR #13. For this archived variant, run `python -B -m unittest tests.test_factory_v3 -v` from repo root in the pinned environment, close protected-output/profile-path gaps, add regression cases for those gaps, and commit/push. Next evaluate the two private original PETEK JPEGs with four explicitly reviewed corners, inspect masks and preserve pixel-difference evidence. Do not invent source geometry approval or claim Windows acceptance. See NEXT_AGENT_TASK.md for commands and acceptance gates.

## Preservation verification

48 changed files are published in PR #14. GitHub tree `80572f87a27f04a8cd4741632b2c11f9dfe0e7bb` matches the locally tested checkpoint tree exactly. All 145 tracked Python files compiled (four inherited invalid-escape SyntaxWarnings, no syntax errors). Clean-checkout source-only builder produced 245 ZIP entries, CRC/hash verified, with the test file present and no image/DB entries. Local build used commit `b6fceca3e2491d99d84672ee2db8e99efb9a7498`, whose tree is identical to remote implementation commit `a950a85b055835231fb30750da9f336f250fcc71`; commit metadata differs. This is candidate-builder evidence, not Windows acceptance.

Dedicated checkpoint CI initially failed because a requirements filename was wrong; fixed to `requirements-core.lock.txt`. The failing run and pending rerun are recorded in TEST_EVIDENCE.md. This packaging configuration correction does not alter rendering.
