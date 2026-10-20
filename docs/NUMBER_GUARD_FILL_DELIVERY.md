# NumberGuard V2 and proportional artwork fill

Consolidates code changes on the PR #9 baseline. No merge of alternative release or PETEK feature branches.

- Exclusive file publication and immutable source snapshots protect against output collisions.
- Monotonic template identity claims retain consumed and historical numbers.
- Review tools and the watcher share no-overwrite helpers.
- Accepted artwork aspect differences use proportional center cropping instead of stretching or gray padding. Orientation and 15% mismatch rejection remain enforced.
- Fix the factory's direct import of the file safety helper.
- Include synthetic collision, failure, historical-number and center-pixel preservation regressions.

Only source, synthetic tests and this general note are published. No machine-specific launchers, runtime data, backup inventories, image samples, approval records or user reports are included in this change. Deployment and private local acceptance are separate from the repository review. This branch remains a draft until its GitHub checks are evaluated.
