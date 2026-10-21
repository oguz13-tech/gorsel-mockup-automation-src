# Next engineer or Astra continuation

1. Read AGENTS.md and active PETEK V3 branch diff before touching any code or Windows runtime.
2. Fetch current PR #9/#11/#12 state. Retain NumberGuard/Fill improvements; DO NOT port fixed 13-slot recipe back as PETEK default.
3. Verify Windows/Ubuntu CI logs, run source-preserving tests and legacy suite. Fix failures and document actual results (not guesses).
4. Visually validate multiple privately supplied real PETEK mockups: variations in vent count, top/low arches, floor, hard shadows, white floor false positives, dark surfaces, extreme camera angles. Keep the real customer images outside public Git.
5. Evaluate improved segmentation/alpha matting only if benchmark proves gains. Current automatic segmentation yields DRAFT requiring human review. Do not auto approve.
6. Reconcile installed portable Günlük V2 with source branch. Do not assume GitHub source equals current Windows binaries. Windows local database and original backup changes require explicit user approval.
7. Build Windows ZIP candidate through scripts/petek_v3_windows_release.py; inspect manifest SHA. Stage in separate directory and pass real Windows acceptance with user.
8. If Astra has private uncommitted Work files, export them and diff against this branch. Preserve branch and PR checkpoint for continued handoff.

No unattended marketplace publication, no default cloud upload. Local PETEK CSV 'Barkod (Dahili)' is not a registered GS1 barcode.
