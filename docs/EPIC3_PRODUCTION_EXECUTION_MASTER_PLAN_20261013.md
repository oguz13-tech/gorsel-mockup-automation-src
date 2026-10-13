# EPIC-3 — CANONICAL PRODUCTION EXECUTION PLAN
**Date:** 2026-10-13 | **Owner:** ChatGPT (architecture, code, gate) | **Local executor:** Kilo (bounded validation only)
**Objective:** Ship the first genuine 3:4 sale-oriented images quickly without treating full autonomous factory completion as a prerequisite.
**Source of truth:** This file + bridge Issue #1 + exact GitHub SHA + current local evidence. Previous handoff references are historical.
**Plan status:** ACTIVE / NOT RELEASED. No live deployment or merge authorized.

## 0. Non-negotiable safety, evidence and role contract
- Runtime workspace: `C:\Users\oguzc\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu`; resolve and verify before running; never assume an old clone is current.
- Source repo: `oguz13-tech/gorsel-mockup-automation-src`; current safety branch: `safety/epic3-archive-guardrails-20261010`.
- Separate code checkout and runtime assets; never run direct migration or factory production to collect diagnostics.
- **ChatGPT:** author/review/test/commit code, assess all findings, select gates. **Kilo:** Windows commands, read-only probes, disposable TEMP sample renders, reports; no coding, modifying repo, changing approval, moving/deleting/restoring, commit/push/merge, or production launch.
- Keep autoapproval OFF. Only active, source-matching, manually approved geometry is eligible. Never stretch H↔V, non-uniformly resize artwork, crop arbitrarily, paint over unreviewed foreground objects, or overwrite originals.
- Original backups, 172 historical archive-only identities, wastebasket and recovery records are not synced/restored automatically; issue of 172 is CLOSED.
- Before any intentionally mutating local operation: explicit user approval, verified backup/rollback, exact SHA, staging plan, fail-closed.
- PASS requires command logs / exit codes / exact SHA / immutable source and DB evidence; isolated smoke PASS is *not* production PASS. Do not mark PR #4 ready, merge or claim production release before gates.

## 1. Current verified evidence baseline
- `main` 97cd5cbad562ffff8904d13b28516f4390430d8b; `feature/epic-3-geometry-accuracy` 3e42cd51262cbdee725db4e4c964cc7b2d3c8368; safety head 2ec8482347fdc6c67a5f016a6958e92b7a55a938 (24 commits after feature). Draft PR #4 OPEN / NOT MERGED.
- Latest safety workflow: https://github.com/oguz13-tech/gorsel-mockup-automation-src/actions/runs/38086997078 — 5 jobs PASS (existing 222 tests, Windows safety 21 tests, visual sheet 6 tests and real synthetic smoke).
- Kilo verified 46/46 APPROVED+hash-valid records by category: WiFi 31, glass vertical 1, glass horizontal 1, wood 1, cutting-board 1, backsplash 11; six actual-template 1200×1600 isolated TEMP smoke images PASS, but used artificial prints.
- Candidate sheet audit COMPLETE: 31 approved WiFi from 175 physical, and 78 physical cutting-board candidates with only 1 APPROVED. Kilo contact sheets: `%TEMP%\epic3-visual-candidates-40y2kb3w\WIFI_APPROVED_PAGE_01..03.jpg` and `CAM_DOGRAMA_ALL_PAGE_01..06.jpg`. Nine pages await owner visual review.
- Last report: https://github.com/oguz13-tech/gorsel-mockup-ai-bridge/issues/1#issuecomment-6102306196. Temp paths are provisional; Windows TEMP cleanup may remove them.
- Demonstrated image-quality concern: cutting board looks like framed picture; WiFi lid not convincingly integrated. 4 other representative scenes looked promising, not final certified.
- CI coverage gap: `tests/test_surface_mode_detection.py` not in safety workflow's full-regression command. Unmerged `epic3-geometry-fix` adds `generate_white_panel_quads()` and backsplash detection corrections. Determine compatibility before cherry-picking.
- `scripts/epic3_validation_bundle.py` hardcodes EXPECTED_BRANCH=`feature/epic-3-geometry-accuracy`; it cannot serve as exact safety-branch gate unmodified.
- Unverified: actual current factory Doctor/preflight, required manifest and both H/V masters, cloud credentials, AI dependencies/cache, output permissions, genuine artwork pilot, GUI acceptance, full production Excel/upload/persistence/resume.
- Golden GT provenance and some older WiFi legacy corners were questionable. A high IoU against suspect GT is not physical-surface correctness proof.

## 2. Definition of done by release level (DO NOT collapse)
**R0 — isolated realistic first JPG:** one real user-supplied design (or pair where orientation demands) in a disposable output root, 1200×1600, correct visual perspective, no live input mutation, no upload or Excel. Human accepts scene. Not a commercial-factory release.
**R1 — local small-batch render:** user-approved subset of 4 priority categories (glass V, glass H, wood, backsplash); explicit subset selection, safe local-only render CLI or isolated source, no mandatory cloud/Excel; all images QA+manifest; resume/collision/return-code evidence; human accepts.
**R2 — six-category controlled production:** image quality accepted for WiFi and cutting board as well; true occlusion test, correct physical orientation, controlled deployment and rollback; one complete real batch with source immutability.
**R3 — full autonomous commercial workflow:** output state, ImgBB/FreeImage, Excel, SEO and multi-store distribution, stage watcher, long-run recovery and performance tests; CI gates and manual review.
No forced R3 implementation before R0/R1.

## 3. Workstreams with owner, prerequisites and exit evidence
### P0-A — Local current reality snapshot [Kilo, NOW, 20–45 min]
On a NEW TEMP code checkout pinned to exact safety SHA, run read-only Factory Doctor --fast and factory preflight, optionally compare with previous reports. Capture complete `DOCTOR_JSON` and `PREFLIGHT_JSON` with secrets redacted, literal return codes, resolved runtime root, actual manifest presence/item count, missing H/V masters, profile usability per category, occlusion AI needs/masks, cloud configuration present (NEVER reveal keys), output paths/permissions, baseline DB SHA before/after. Do not alter live files, source, database or approvals. If imports unexpectedly create live mutable files, STOP and report.
**Exit:** one issue comment including actual blockers in machine-readable section, no fabricated ready state.
### P0-B — Code readiness and coverage [ChatGPT, PARALLEL]
On dedicated source-only branch based on exact safety SHA, inspect unmerged backsplash fix, port only independently verified narrow corrections, add surface mode tests into CI, align validation bundle branch policy safely (avoid generic bypass), run Windows+Linux tests. No merging prior to evidence.
**Exit:** exact commit + passing CI + diff/rationale and safe rollback.
### P0-C — Local-only production path [ChatGPT, PARALLEL after feasibility]
Implement minimal opt-in `render-only` path (or safe wrapper around existing production renderer) with bounded explicit template IDs, designs and TEMP/pilot output; skip network, SEO, Excel, long-lived user DB writes; use approved+hash-matching geometry, physical H/V, masking fail-closed, quality gate, output collision protection and manifest. Avoid invasive rewrite of full V5 factory. Tests synthetic and real-render fixture; output paths outside live runtime for pilot.
**Exit:** one-button/one-command invocation docs, 3:4 output quality, repeat run idempotence, no DB/assets mutation and no provider credentials required.
### P1-A — Select visuals and actual artwork [User + ChatGPT; can run now]
Review nine generated contact-sheet pages, including whether image previews preserve aspect (yes). Record a shortlist of WiFi approved templates and cutting-board alternatives to take through human review. Ask for 1 H/V genuine user design pair, or clearly identify an existing pair in manifest. Do not approve other templates automatically.
**Exit:** chosen template IDs and actual user-approved artwork; identify invalid scene types.
### P1-B — Real product pilot [Kilo TEMP executor + user acceptance]
Run tested local-only renderer using exact code SHA, one actual print per 4 priority categories, before/after hashes, output 1200x1600, overlay/orientation/text crop/black borders/occlusion/sharpness judgement. Report errors by category rather than repairing ad hoc. No cloud calls.
**Exit:** human-approved set of true commercial mockup JPEGs.
### P1-C — QA and retry [ChatGPT]
Repair only demonstrated rendering defects, add targeted regressions, rerun pilot. No blind tuning or GT-derived auto approvals.
**Exit:** repeatably acceptable small batch; manifest/summary.
### P2 — Controlled release (permission gate)
Full read-only preflight, native backup/restore rehearsal, source/runtime version map, exact pinned release SHA, dry-run, opt-in deployment, smoke after deployment, reproducible rollback. Only with explicit owner permission.
**Exit:** normal UI launches correct source and resume/skip results, no input drift.
### P3 — Complete backlog (do not block early image creation)
Full factory cloud API keys configured securely; cloud upload retry/rotation, Excel integrity, SEO and multi-store; full 492-template assessment (not automatic promotion); bulk UI analysis progress and result modal, independent tool center 8 launchers, number collision and tombstones, watcher staging recovery, on-plan frontend mapping, Grounding-DINO + SAM on representative occluders, independent golden GT quality subset, real Windows lifecycle transaction tests, duplicate UI legacy editor/input drift and state consolidation, UX/performance and restore drills.
**Exit:** end-to-end real production at chosen scale with evidence and operator handbook.

## 4. Explicit discovered technical risks / deferred decision log
- One `APPROVED` geometry ≠ product photo is correct; cutting-board visual quality still BLOCKED.
- `factory_preflight` imposes manifest/H/V/cloud prerequisites; six-sample TEMP smoke bypassed full production preflight. R0 local-only must preserve safety while removing unrelated cloud dependencies.
- Potential legacy input split: root `SABLON_DUZELTICI.py` vs modern 8080 app; `1_TASARIMLAR` vs `MOCKUP A HAZIR GORSELLER` in older entrypoints. Choose single operator path for release and archive unused launchers later.
- `INCELEME_MERKEZINI_AC.ps1` starts a watcher and may touch runtime, so do NOT run it as a read-only health check.
- Some app modules `init_db()` on import; diagnostic subprocess must be treated as potentially mutating until verified in current runtime. Hash-before/after alone misses create/delete/side effects; log suspected changes and STOP rather than repeating.
- No automatic destructive sync of 794 original archive vs 621 working files, no re-count of 172 historical archive-only IDs.
- Automation quality is human-review-gated, not fully automatic approval ready. Commercial scope and 3:4 marketplace format should be independently accepted.

## 5. Execution sequence and target estimates (engineering estimates only)
- **Today:** P0-A read-only diagnostics + P0-B CI gap work + review nine sheets/P1-A in parallel.
- **R0 realistic initial images:** ~2–5 engineering hours after required genuine design, safe local dependencies and confirmation of minimal pilot invocation.
- **R1 safe small batch:** ~1–2 working days if local-only path passes.
- **R2 six categories:** ~3–7 working days, subject to cutting-board review/occlusion.
- **R3 full automation:** 2–4+ weeks; separate commercial release roadmap.
If P0 uncovers blockers, estimate must be revised from evidenced failure; no invented fixed completion time.

## 6. Reporting and no-repeat policy
Every Kilo task must use a fixed SHA and single issue comment; no unbounded rereview. ChatGPT independently verifies logs and tests before delegating next batch. Never repeat archived 172 comparison or prematurely merge PR #4. Use plain `READY/BLOCKED` per gate, with why and owner. At least one task should move the user toward genuine local JPG output rather than collecting only static reports.
