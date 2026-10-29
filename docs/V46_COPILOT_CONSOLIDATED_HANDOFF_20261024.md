# V4.6 — Windows Copilot handoff / consolidated release (2026-10-24)

> **DO NOT MERGE** this branch until the actual installed V4.6 source baseline has been reconciled. This branch starts from V4.5 PR #48 head (\`35a04577294307b0c72452f0614776382e7965fd\`), because current V4.6 Windows ZIP/source is **not yet represented completely on GitHub**. Existing main is older. These initial V4.6 changes are standalone and are *not* proof the whole V4.6 is in GitHub.

## Human acceptance already done: do not repeat
- Real-ESRGAN official installation with hotfix; NVIDIA RTX 3060 Laptop GPU 64×64 Vulkan **GPU_SMOKE_PASS**. One 2880×3840 photo output visually accepted, no distortion. Fast model missing: don't select it.
- V4.5 manual approved four-corner edit persisted after reopen and was used by one real render (PASS).
- V4.6 UI, bulk selection and '4 Köşesini Algıla (Taslak)' action functional. Draft corner accuracy **FAIL / explicitly deferred**; never auto-approve its results.
- Two SQLite DBs pass integrity checks; all template count 708. Current profile row count 591 (previously 590; NOT exact active-approved count).
- G3 output ledger: 111 artifacts; 110 RENDERED, 1 REVIEW_REQUIRED; 75 verified, 35 missing, 0 SHA mismatch, 0 unsafe paths. User said they intentionally deleted some past rendered files to make disk space; DO NOT purge records or claim all 35 intentionally deleted without comparing path-by-path.

## Critical protected Windows data
- Live user-owned workspace: \`%USERPROFILE%\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu\`
- Installed candidate: \`C:\GorselMockup_V46_ADAY\GORSEL_URETIM_MERKEZI_V46_4KOSE_TOPLU_YANSIMA_ESRGAN_WINDOWS_TEK_PAKET\`
- Current local development copy: \`C:\AI_WORK\GORSEL_V46_COPILOT_CALISMA\GORSEL_V46_COPILOT_TEMIZ_KAYNAK_20261024\` (actual folder name may differ; detect from workspace).
- Never modify installed files, live SQLite, approved quad profiles, original template images, masks, 4K output, previously rendered images, or production ledger directly.
- Never upload private customer imagery, SQLite or Golden source photographs to public GitHub. Do not copy user data into git staging.
- No automatic GitHub merge, destructive commands, recursive cleanup, unapproved restore or write to live OneDrive.
- Work only on isolated local Git branch/worktree. Source reconciliation must be done with *content/hashes* not blind replacement of older code.

## Existing code in this branch
- \`MERKEZ/port_transition_v46.py\`: fixes gentle \`taskkill /PID\` failure when Windows requires \`/F\`: recheck exact PID+cmdline+old V4.x allow-list, return False to enable GUI's second explicit confirmation, force only after human approval. **No generic force kill.**
- \`TESTLER/test_port_transition_force_fallback.py\`: 6 mocked safety cases. Separate isolated Python tests PASS locally; **Windows human GUI acceptance still pending**.
- Need integrate against actual V4.6 \`MERKEZ/merkez.py\` already containing the two-stage approval UI before claiming runtime works.

## Work queue — do not turn into whole-repo unlimited credit scan
1. **S0 Current baseline reconciliation**: Inspect only V4.6 files required for next patch (see above), compare with this branch's V4.5 base; mark what is missing from GitHub without changing live runtime. Bring known-safe V4.6 source changes to this development branch as necessary; isolate commits, keep \`main\` unchanged.
2. **P0 #49**: integrate 8080 transition and run targeted regression Windows tests. Current branch has safe module + mocks but not full GUI integration proof.
3. **P0 #50**: fix cross/plus-shaped glass reflection rejected by user. Four glass families (Cam Dikey, Cam Yatay, Cam Doğrama, Ocak Arkası); realistic category-specific window/spot reflections *similar to privately supplied references*, preserve artwork detail and mask exterior, choose new A/B output names, do not overwrite old renders. Human comparison gate for 4 samples is required.
4. **P1 #51**: protect high-upscale results from cropping/artwork degradation, output verification and no overwrite. Delete only redundant *dedicated* 4K XLSX/report generation in next release; **never remove marketplace SKU / HTTPS / Excel workflow**. Prefer user-friendly 4K file location; preserve 4K SHA receipts, backward compatibility, old paths and idempotence.
5. **P0 #32 #35**: PETEK mask/slots/curves/shadows Golden QA. Smoke tests; do not assume PASS without review. Marketplace Excel ImgBB HTTPS link mapping + SKU/columns requires separate verification.
6. **P0 #35**: read-only audit: distinguish user-deleted render vs unexplained missing output with evidence, retain receipts. Add a truthful counter for active APPROVED rather than total \`template_profiles\`; explain stale status. Batch 10 → 100 → 1000 only after approval.

## Definition of completion
- Unit/isolated tests, Windows real smoke, data integrity/rollback evidence and four-category human photo QA. Completed code is not a Windows PASS.
- One consolidated later Windows ZIP, one README, file hash manifest; no intermediate ZIP installation without user authorization.
- Keep test output concise and explicit: PASS / FAIL / BLOCKED / deferred.
- User has Copilot Student limited AI credits (199/200 as of 2026-10-24). Avoid unlimited exploration, repeated entire repo indexing, and re-running successful tests. Focus on one module/task per agent session.

Related: #35 acceptance gate, #36 program map, #49 port transition, #50 reflection, #51 Real-ESRGAN.
