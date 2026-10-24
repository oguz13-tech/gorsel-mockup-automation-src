# V4.6 All-Category Geometry Evidence

The benchmark is isolated and synthetic-only. It does not read production
SQLite, approved profiles, original templates, or customer images.

| Category | Real samples | Synthetic samples | Detection | Median IoU | Failure / wrong-object count | Status |
|---|---:|---:|---:|---:|---:|---|
| Wi-Fi Kutusu | 0 | 3 | 100% | 0.9824 | 0 | HUMAN_REVIEW_REQUIRED |
| Cam Tablo Dikey | 0 | 3 | 100% | 0.9826 | 0 | HUMAN_REVIEW_REQUIRED |
| Cam Tablo Yatay | 0 | 3 | 100% | 0.9808 | 0 | HUMAN_REVIEW_REQUIRED |
| Ahşap Tablo | 0 | 3 | 100% | 0.9833 | 0 | HUMAN_REVIEW_REQUIRED |
| Cam Doğrama | 0 | 3 | 100% | 0.3579 | 0 | HUMAN_REVIEW_REQUIRED |
| Ocak Arkası | 0 | 3 | 0% | 0.0000 | 3 | HUMAN_REVIEW_REQUIRED |
| PETEK Dolabı | 0 | 3 | mask-only | n/a | outside-mask preserved: true | HUMAN_REVIEW_REQUIRED |

## Interpretation

- The four high-contrast rectangular synthetic categories are a regression
  baseline only; they are not real-template acceptance.
- Cam Doğrama requires a category-specific frame/occlusion-aware detector.
- Ocak Arkası is intentionally not assigned coordinates after all synthetic
  detections failed. It remains `DRAFT/REVIEW_REQUIRED`.
- PETEK is measured as a mask property, not forced into a four-corner rule.
  Independent upper/lower curve regions and slot preservation require real
  Golden samples for acceptance.
- The real Golden sample count is zero in this safe package. No category is
  declared real PASS.
