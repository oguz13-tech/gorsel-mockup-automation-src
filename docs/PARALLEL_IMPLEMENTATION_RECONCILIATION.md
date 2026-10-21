# Parallel implementation reconciliation — 2026-10-21

## Confirmed current main candidate

- PR #13: https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/13
- Branch: `feature/petek-v3-source-preserving-factory-20261021`
- Head inspected: `ca6314af44491136373a0c807df732403c37c71b`
- 37 commits above PR #12, 22 changed files; open draft, not merged.
- Existing five handoff docs were read at that exact commit. TEST_EVIDENCE still describes planned tests, despite successful CI; next writer should reconcile actual evidence.

## Verified CI at PR #13 head

- Full system audit: https://github.com/oguz13-tech/gorsel-mockup-automation-src/actions/runs/39564576191 — Ubuntu and Windows jobs SUCCESS, all pytest step success.
- PETEK candidate: https://github.com/oguz13-tech/gorsel-mockup-automation-src/actions/runs/39564576330 — Ubuntu and Windows SUCCESS. Windows build, ZIP hash inspection and artifact upload SUCCESS.
- Numbering regression: https://github.com/oguz13-tech/gorsel-mockup-automation-src/actions/runs/39564576254 — workflow SUCCESS.
- This is GitHub runner evidence, not user-machine installation or visual acceptance. Exact test counts not inferred from status.

## Why preserve this separate checkpoint

Astra's local code existed before the parallel branch was discovered. It includes a source-mask renderer, manual review UI, seven-category adapter, durable shared queue, stable LOCAL/PDK identities, 22 passing synthetic tests and deterministic candidate builder. None should be lost. But PR #13 integrates into the existing Flask center and is therefore the preferable UI continuation under the user's one-application requirement.

| Area | PR #13 | This preserved variant | Next action |
|---|---|---|---|
| UI | Existing Flask center tab | Separate unified Tk center | Retain integrated Flask direction |
| Artwork fit | Contain with white panel padding | Proportional center crop, optional physical ratio | Offer explicit reviewed fit policy; never silently change output identity |
| Mask | Conservative global luminance/chroma proposal | Neutral-color + local contrast proposal, brush | Benchmark both on private originals before selecting |
| Queue | PETEK-specific ledger | Shared seven-category queue adapter | Port proven durable lifecycle ideas selectively |
| SKU | PK + store group + art SHA | Old LOCAL/PDK formula preserved | Read-only reconciliation needed before changing product IDs |
| Recovery | Uncertain outputs require review | Exact byte-identical orphan adoption | Add cross-process crash tests; preserve fail-closed behavior |
| Packaging | Staging ZIP on Windows CI | Clean-checkout deterministic source ZIP | Fix actual release gaps; avoid duplicate user packages |

## Concrete issues noticed in PR #13 source (not yet repaired here)

1. `scripts/petek_v3_windows_release.py` test BAT refers to `tests/test_petek_v3.py`, but `CODE_DIRS` excludes `tests`; candidate test command will not find its test file. Add explicit tests allowlist and a packaged-test smoke test.
2. Generated launch/test BAT runs pip in `py -3` environment, potentially changing an existing environment. Prefer isolated venv/pinned dependency preparation; preserve working Windows environment.
3. `make_artifact_key` includes source/art/mask/template/recipe but not quad or physical aspect; verify if profile version elsewhere prevents geometry-change reuse, and add a regression before release.
4. Handoff/evidence documents omit new exact head and actual successful CI results. Update through a separate docs/reconciliation PR, not by racing the active branch.
5. Need actual installed Windows package vs GitHub comparison; a newer private Windows candidate may contain changes not pushed. Obtain exact package/build manifest before assuming equivalence.

## Immediate next task

Create a fresh review/fix branch from the current PR #13 remote head, reproduce the packaged-test omission, fix only those packaging and identity gaps with regressions, then update canonical handoff/evidence via draft PR. Compare this archival queue/mask code only after that. Original photos remain private; no automatic merge, live install or migration.
