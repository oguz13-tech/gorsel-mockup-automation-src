# V4.10.1 Github ↔ Windows ZIP — FULL SOURCE SYNC PROOF

**Result: 482/482 exact source blob matches.** Verified on 2026-10-31 via independent local Git blob computation and GitHub recursive Git Tree listing.

- GitHub repository: `oguz13-tech/gorsel-mockup-automation-src`.
- Branch: `release/v4101-source-and-windows-audit-20261031`.
- Matched source tree commit: `a1e6057b0fd0f80461f8b5a01243c744e0412444`.
- Matched source tree SHA: `6d4cd38317905277deb8c5268850290d740ef2d8`.
- GitHub tree recorded **611 blob entries**, including **482 ZIP paths** and **129 historical files** inherited from older V4.6 branch.
- **Missing ZIP paths: 0. Content mismatches: 0.** All 482 match their Git blob SHA1 computed locally from fresh-extracted ZIP bytes using standard `sha1("blob "+byte_length+"\\0"+bytes)`.
- ZIP archive SHA256: `4b5b06fa8392aa28bf8d9fa70ccc90a799a8acb8681a69cd143aecdeec57a1f8`.
- ZIP inner `SHA256_MANIFEST.json`: **481 tracked files verified**, plus the manifest itself (=482 checked against Git tree). The manifest omits self to avoid cyclic hash.
- GitHub original branch `feature/v46-safe-consolidation-20261024` was left intact. The package files were committed to a **separate release source branch**.
- This file and `V4101_AI_DEV_HANDOFF.md` are **additional GitHub-only documentation** created after the ZIP was built and are not part of the 482-path package manifest; their presence does not invalidate source matches.
- The repository contains older files not in the ZIP. The canonical V4.10.1 file list is **only the 482 source paths in this proof**, or the 481 manifest entries + `SHA256_MANIFEST.json`. Read `docs/V4101_SOURCE_FILE_INDEX.md` for list.
- **WINDOWS_NOT_VERIFIED:** Source sync and build tests do not prove the real user-specific PETEK HTTP, GPU/4K or store/Excel runs. Do not merge as a stable production final without explicit user acceptance.

### Reproduce in a clean clone

```bash
git checkout release/v4101-source-and-windows-audit-20261031
python scripts/v4101_verify_package.py
python -m compileall -q MERKEZ SABLON_V2_MIMARI scripts tests
find SABLON_V2_MIMARI/static/js -name '*.js' -print0 | xargs -0 -n1 node --check
```

### Required next steps
- Run GitHub CI check and Windows live acceptance (see `docs/V4101_WINDOWS_ACCEPTANCE.md`).
- Full V4.10.1 ZIP is the user deliverable; archive assets have not been uploaded to GitHub Release, so **GITHUB_RELEASE_ASSET_NOT_PUBLISHED**. This is separate from the fully synced GitHub *source* tree.
- The old branch and 129 inherited historical-only paths must be clearly tagged in future canonicalization; do not delete until their role has been checked.
- Open issues #66, #67, #68, #69, #70, #71 and #72 remain open for partial feature acceptance and bugs.

**Scope of proof:** exact released source bytes → Git tracked blob SHA1, not subjective Windows functionality.
