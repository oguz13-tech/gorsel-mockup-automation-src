# V4.6 Rollback

- Close the V4.6 window and any process started from the candidate folder.
- Keep the prior installed candidate and live workspace untouched.
- Remove only the newly extracted candidate folder after confirming its exact path.
- Do not restore, migrate, or overwrite SQLite, approved geometry, masks, source
  templates, receipts, or prior outputs from this document.
- If a source hash, receipt, or output differs, stop and mark the item
  `REVIEW_REQUIRED`; do not repair it automatically.
