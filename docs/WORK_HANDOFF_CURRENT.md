# Sprint 2 checkpoint — 2026-10-21
Branch fix/final-18-no-loss-identity; base PR26 3a771533977255d9ec2b9f28b1d8c9c3dea45539. Resolve latest commit via git rev-parse HEAD.
Milestone A implemented: reproduced same-key/different-image physical-aspect bug with failing real synthetic render test. Version-2 canonical identity binds source/art/mask, UID, float32 renderer quad, physical ratio, current recipe, actual contain-white fit and marketplace dimensions. Missing geometry fails closed. Batch derives seller-specific job key from render key, verifies returned key, writes exclusive receipt with identity/output SHA, validates receipt on reuse. New SKU uses job key so different mockups do not collide. Old ledger/SKU/profile/output rows are neither migrated nor rewritten; old v1 jobs are not silently reused.
22 synthetic Linux tests PASS; Windows/Ubuntu CI pending for this commit. Native Windows acceptance not run.
A limitations: receipt partial-write crash fails closed and needs review (no automatic repair); source read/hash race and full adversarial concurrency remain B work.
B/C and private V3.7 reconciliation remain incomplete. No merge/live install/user data changes.

## Milestone B partial checkpoint
Added 32 concurrent reservations through 8 independent SQLite connections, immutable same-key/different-SHA collision check, missing-receipt quarantine/no-overwrite test. Red regression proved ledger.rendered could accept nonexistent output; fixed with BEGIN IMMEDIATE and output existence/symlink/SHA verification before SUCCESS. Linux full PETEK suite: 24 PASS. These are threaded connections, NOT two native Windows processes. B still open: multiprocess kill/restart, stale lock, Unicode/extension/numbering matrix, audit chain. C 100-item batch still open.
