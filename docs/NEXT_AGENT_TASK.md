# Next agent — executable continuation without chat history

## First action: reconcile with the already advanced PR #13

The MAIN continuation is `feature/petek-v3-source-preserving-factory-20261021` at
`ca6314af44491136373a0c807df732403c37c71b`, PR #13. This checkpoint is an alternative
implementation preserved for code-loss prevention. Do not replace the integrated Flask UI
with a second permanent Tk program. Selectively port useful queue/tests/render fixes after
comparison, on a fresh branch from current PR #13. Read PARALLEL_IMPLEMENTATION_RECONCILIATION.md.

## Preserved checkpoint

Repository: `oguz13-tech/gorsel-mockup-automation-src`.
Branch: `checkpoint/astra-petek-v3-local-20261021`.
Read `AGENTS.md` and these five docs before modifying code. Fetch the remote branch and inspect `git status`; never force-push. This is a one-writer branch. If another writer advanced it, create your own branch and coordinate through a draft PR. Do not merge any PR.

## 1. Verify the saved code

From a clean checkout, use an isolated Python environment and root `requirements-core.lock.txt`.
Run `python -B -m unittest tests.test_factory_v3 -v` and the existing full test command in `.github/workflows/epic3-full-audit.yml`. Inspect the new Windows/Ubuntu Factory V3 workflow for the exact head. Record actual results, not assumptions.

## 2. Immediate next implementation

Close protected-path validation gaps before a release: `app.py:review`, `petek_v3.py:save_profile`, and `production.py:LegacyAdapter`/`run` must prevent any output/profile/legacy_store writes under live runtime, original archives, code or backup directories, including junctions/symlinks and relative paths. Preserve legitimately separate new state directories. Add adversarial regression tests. Bind review/save to immutable source bytes and the displayed source SHA to remove TOCTOU gaps. Commit/push a checkpoint and update handoff.

## 3. Real-source mask evaluation

Two original PETEK images were supplied privately by the user: `petek-mockup1.jpeg`, `petek-mockup2.jpeg`. They are NOT in GitHub and must not be uploaded there. If your environment lacks them, request only these files or use the user's private attachments. Old output examples `PETEK_3cfcab42d2102f944fd481c8.png` and `PETEK_6ae2fff51edca77b6af12ef2.png` show blurred padding/artificial slots. Use private examples for evaluation only.

The user agrees to manually marking four front-panel corners. A source quad chosen by an agent for experiments is not user-approved production geometry. Evaluate segmentation and compositing, show before/after and mask preview, measure protected pixels relative to the formatted source, inspect actual holes/curves/floor/bevels. Never reconstruct original source from an already printed output. No fixed 13-hole requirement remains. Record failures honestly. Original physical aspect is optional; label estimated aspect.

## 4. Finish the factory and release gates

Keep PR12 old six-category core unchanged unless a tested regression demands a change. Complete common-queue six-category integration coverage, safe legacy stale-lock recovery, process-kill recovery, native Windows GUI tests, exact dependency policy, clean candidate build and safe backup/activation/rollback tooling. Preserve all filenames, approved corners and original archives. No live DB migration or install without the user's required explicit approval. No marketplace/cloud sending.

## 5. Build and checkpoint

`python scripts/build_windows_factory.py --output <outside-repo>/candidate.zip` creates a candidate from tracked clean source, independent of the previous agent workspace. Do not include live configs, private images, customer files, credentials or operational evidence in public commits. Update WORK_HANDOFF_CURRENT, ARCHITECTURE_DECISIONS, TEST_EVIDENCE and WINDOWS_RELEASE_STATUS at every meaningful checkpoint. Keep unfinished but compile/testable work in the draft PR. A final Windows package and human acceptance are still required by the original task.
