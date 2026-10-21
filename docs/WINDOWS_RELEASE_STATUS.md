# Windows release status — NOT FINAL / acceptance pending

## Working Windows vs GitHub

The previously delivered V2 Windows center contains fixed 10-template/six-category daily production plus a separate PETEK procedural/commerce route. The original private Windows daily baseline depended on a verified PR9 source backup plus NumberGuard/FILL overlays. GitHub PR #12 contains the sanitized operational overlays but not the user's runtime data.

This branch adds a single V3 factory GUI, reviewed original-detail masks and a common local ledger. The user's installed Windows runtime has **not** been changed. Never infer current Windows code from GitHub HEAD alone. Check installed code hashes through existing readonly verification.

## Rebuild from GitHub

1. Checkout the exact active branch commit; use a clean worktree.
2. Python 3.11+ recommended. `python -m pip install -r requirements.txt` in an isolated environment (existing production environment must not be modified).
3. `python -B -m unittest tests.test_factory_v3 -v`.
4. `python scripts/build_windows_factory.py --output <outside-checkout>/GORSEL_URETIM_FABRIKASI_WINDOWS_ADAY.zip`.
5. The builder includes source, tests, docs, Windows launcher and SHA256 manifest. It excludes photos, DBs, live `ayarlar.json`, private settings and untracked files.
6. Extract to a NEW folder. `KABUL_TESTI.bat` runs synthetic tests; `BASLAT.bat` opens V3. Neither overwrites the installed application. This is a candidate, not approved unattended production.

## Required local material (never publish)

- Existing source tree with verified installed NumberGuard/FILL version.
- User-selected live runtime directory and original template pools.
- Verified backup directory containing `PR9_SOURCE`, `RUNTIME_BACKUP`, and `RUNTIME_BACKUP_SHA256.json` for old categories.
- Human-approved source profiles and exact template matches.
- Real PETEK original JPEG/PNG, manually reviewed four corners, approved source-bound mask.
- Design folder outside code/runtime/backups/output. All photos and customer data stay local.

Paths are configurable in the GUI. Generic defaults use `C:/AI_WORK/...`, `C:/AI_LOCAL_OUTPUTS/...`; no private username or historical backup timestamp is embedded. Old archived V2 backup markers are placeholders and are not runnable configuration.

## Dependency gap

Root requirements are inherited from PR #12. Local new tests ran newer installed CV/numpy/Pillow versions (see TEST_EVIDENCE). CI on pinned dependencies must pass, followed by a Windows probe. Launcher discovers an existing environment, but does not yet enforce exact versions or install offline wheels. No dependency install was performed on the user's PC.

## Backups and rollback

No live files are replaced by the candidate. Keep the current Windows installation and verified original backup intact. Before any future in-place activation: inventory + hash code and live file metadata, verify a separate backup, stage candidate, run clean tests, perform actual limited visual acceptance, obtain required explicit activation approval.

Rollback for the current side-by-side candidate: finish/stop the current job, close V3, launch the old verified BASLAT.bat. New output/ledger/profile files remain separate and must not be deleted by rollback. A final automated code-backup/activation/rollback tool is **not yet implemented or validated**; do not claim it exists.

## Remaining release gates

- Protected-output path and source snapshot audit, additional safety tests.
- Full six-category regressions and Windows adapter execution.
- Original PETEK source masks, before/after comparisons and human acceptance.
- Robust legacy stale-lock recovery, process-kill tests and unified review behavior.
- Clean build reproducibility and Windows launch/test acceptance.
- Final dependency policy and backup/activation/rollback automation.
- Existing custom commercial identity reconciliation if non-default prefixes/groups exist.

**Current answer: development is preserved and testable; unattended serial-production final is NOT approved.** No migration, live install, marketplace submission or GitHub merge occurred.
