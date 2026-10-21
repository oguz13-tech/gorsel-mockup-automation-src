# Active PETEK V3 agent handoff

Repo: oguz13-tech/gorsel-mockup-automation-src
Branch: feature/petek-v3-source-preserving-factory-20261021
Branch starting commit: 7d4d42a6b0ec8015a4080e8e6cdcec71b13cecb8 (PR #12, based on PR #9)
Old PETEK: PR #11 49a169806c84686db789f5906563d87006caf5a8 (DRAFT, separate).

## Actual code changed
- SABLON_V2_MIMARI/core/petek_surface_v3.py — source preservation, no 13-slot model, anti-blur bounds, immutable output.
- SABLON_V2_MIMARI/core/petek_mask_store.py — private SHA-bound profiles, draft/edit/human approval.
- SABLON_V2_MIMARI/core/petek_v3_routes.py — local guarded Flask endpoints, native one-window tab.
- SABLON_V2_MIMARI/templates/petek_v3.html — mask editor and local batch controls.
- SABLON_V2_MIMARI/static/js/petek_v3.js — browser 4-corner selection and paint.
- SABLON_V2_MIMARI/core/petek_serial_factory.py — local-only batch, resume ledger and Excel/CSV.
- SABLON_V2_MIMARI/core/petek_factory_adapter.py — isolated entry into existing renderer.
- Existing category identity, rule, UI index, app register, factory catalog adapted only for PETEK.
- scripts/petek_v3_windows_launcher.py + scripts/petek_v3_windows_release.py — Windows staging and safe source ZIP.
- tests/test_petek_v3.py and GitHub Actions candidate workflow.

## Non-negotiable
Read AGENTS.md first. Original templates, ayarlar.db/json, approved 4 corners and OneDrive backups were not changed during repository development. No PR merge, no Windows installation, no private photos or API keys in public Git.

## Release reality
Code on this branch is a CANDIDATE. It is not a proven final Windows commercial production release until tests, Windows customer-machine run, correct source masks and visual acceptance are complete. Automatic candidate masking is not semantic ground truth. Existing six-category full commerce workflow still has separate release gaps.

## Next resume
Read docs/ARCHITECTURE_DECISIONS.md, docs/TEST_EVIDENCE.md, docs/NEXT_AGENT_TASK.md and docs/WINDOWS_RELEASE_STATUS.md; inspect latest PR head and CI logs. Compare with future Astra Work artifacts without blind merging or overriding legacy approved data.
