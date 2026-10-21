# FINAL RELEASE GATES & TAKEOVER MAP — 2026-10-21

## Non-negotiable product definition
One Windows application managing seven categories while keeping the previous six categories' geometry approvals and professional tools. PETEK uses the source photo's real existing slots/arches, source-bound reviewed masks, aspect-correct design projection, and natural lighting/shadows. Photos and customer data remain private/local.

## Canonical task register
**START HERE / Astra task:** https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/24

| Order | Ticket | Focus | Initial status | Acceptance dependency |
|---|---|---|---|---|
| 1 | [#15](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/15) | Source preservation / PR13, PR14, private V3.7 reconciliation | OPEN / NOT VERIFIED | Draft branch/PR, packaging test fix, SHA/provenance |
| 2 | [#18](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/18) | Collision-proof naming, immutable data, SKU + recovery | OPEN / NOT VERIFIED | Concurrent same-name/different-content/extension tests and restore |
| 3 | [#16](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/16) | Mask/geometry UX, upper/lower curves, zoom/pan, Ctrl+Z, brush clip | OPEN / NOT VERIFIED | Real user curve error no longer repro, exact source pixels |
| 4 | [#17](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/17) | Contrast, natural highlight/shadow, optional frame/bleed A/B | OPEN / NOT VERIFIED | Real art/mask before-after and visual acceptance |
| 5 | [#19](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/19) | Unified seven-category center + old tools/profiles | OPEN / NOT VERIFIED | Seven categories, old approvals and tools proven unchanged |
| 6 | [#20](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/20) | Durable batch, QA queue, SKU/Excel, pause/resume | OPEN / NOT VERIFIED | Batch recovery and output/source reconciliation |
| 7 | [#21](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/21) | Real golden set, 34 PETEK results, CI and QA gate | OPEN / NOT VERIFIED | Windows and real-photo evidence, no false automatic approvals |
| 8 | [#22](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/22) | Short clear Turkish UI and terminology | OPEN / NOT VERIFIED | Source mockup ≠ print design, screen-size/keyboard smoke |
| 9 | [#23](https://github.com/oguz13-tech/gorsel-mockup-automation-src/issues/23) | Final independent Windows release, backups and rollback | OPEN / NOT VERIFIED | Physical Windows acceptance + rollback drill |

## Source topology (verify again before coding)
- PR #9 and #12 legacy hardening/NumberGuard; #11 old artificial 13-slot PETEK code is NOT the required production renderer.
- PR #13 Flask-integrated draft, observed `ca6314af44491136373a0c807df732403c37c71b` (not merged).
- PR #14 preserves Astra's parallel Tk implementation, observed `b936a6b8ad292fad239bc7183c38a0f4964c2d7a` (not merged).
- Private Windows V3.7 `GORSEL_MOCKUP_WINDOWS_V3_7_MANUEL_KAVIS_DUZELTME.zip`: not in this repo; ask for it only when needed for selective integration. User can access it via original ChatGPT artifact. Do not publish its real photo fixtures.
- Old installed Windows data and source approvals have NOT been migrated. Prior V3.7 Linux Xvfb reported 48/48 synthetic tests; not final Windows user acceptance.

## Save-before-quota practice (critical)
1. Before large work verify GitHub current head and snapshot local state. **One agent writes one dedicated branch.**
2. Work in a narrowly scoped change, run named tests, make commit+push **before** beginning next change.
3. For every ticket, comment: implementation files, SHA, exact tests, result, risks, failed/untested items.
4. Update `docs/WORK_HANDOFF_CURRENT.md`, `docs/NEXT_AGENT_TASK.md`, `docs/FINAL_RELEASE_STATUS.md` on the active implementation branch. Start any docs-only change on a separate docs branch.
5. If quota expires: last good commit must be remote; handoff states next exact file/line/task/test command, staging environment and missing private inputs. Never say 'completed' solely due to a previous synthetic test or an uninstalled private ZIP.

## Safety gates — do not violate
- No auto-merge, force push, destructive rename/delete, DB backfill/migration, marketplace publish, cloud uploads, or in-place installation.
- No uploads of customer files, original mockups, approved masks, private SQLite, images or workspace secrets into public GitHub issues/repo/CI.
- Any future activation needs explicit user approval and verified backups. Original source pixels outside masks unchanged by the PETEK renderer.
- White border and micro-bleed are **experiments**, not default fixes. Wrong mask cannot be repaired by frame alone.

## Required final evidence
- Exact final source SHA, reproducible source ZIP with verified SHA256 + dependencies.
- Windows startup and seven-category smoke evidence.
- Golden dataset comparative render evidence with lighting/shadow/curve/safe-mask inspection.
- Name/content collision + extension identity + interrupted job + concurrent producer + rollback tests.
- Per-item receipt, products CSV/XLSX and deterministic SKU/identity audit.
- User review and accept/reject record per real template. Final status reflects unmet gates.
