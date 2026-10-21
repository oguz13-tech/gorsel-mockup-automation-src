# NOT FINAL
Sprint2 A implemented; Linux 22 tests pass, new Windows/Ubuntu CI pending. Native Windows acceptance absent.
B/C, private V3.7 integration, seven-category golden QA and Windows final rollback remain open. Existing six-category source untouched.

## Milestone B partial checkpoint
Added 32 concurrent reservations through 8 independent SQLite connections, immutable same-key/different-SHA collision check, missing-receipt quarantine/no-overwrite test. Red regression proved ledger.rendered could accept nonexistent output; fixed with BEGIN IMMEDIATE and output existence/symlink/SHA verification before SUCCESS. Linux full PETEK suite: 24 PASS. These are threaded connections, NOT two native Windows processes. B still open: multiprocess kill/restart, stale lock, Unicode/extension/numbering matrix, audit chain. C 100-item batch still open.

Brush hotfix is partial: GitHub Flask code only; private Tk symptom/real screenshots/cleanup QA remain open. Not a Windows final delivery.
