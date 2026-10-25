# Reference-guided OWLv2 decision report

## Scope

- Recorded rows: **528** across **6** categories.
- Model/API: `google/owlv2-base-patch16-ensemble` / `Owlv2ForObjectDetection.image_guided_detection`.
- Query input: `reference_product_crop`.
- Reference crops are derived from legacy unverified geometry and are not approved ground truth.
- Every row remains `UNKNOWN_GT`, `REVIEW_REQUIRED`, and `geometry_approval=NOT_ALLOWED`.

## Coverage

| Category | Rows | Targets | Reference counts |
|---|---:|---:|---|
| 01_Wifi_Kutusu | 84 | 21 | 1=21, 3=21, 5=21, 10=21 |
| 02_Cam_Tablo_Dikey | 92 | 23 | 1=23, 3=23, 5=23, 10=23 |
| 02_Cam_Tablo_Yatay | 92 | 23 | 1=23, 3=23, 5=23, 10=23 |
| 03_Ahsap_Tablo | 92 | 23 | 1=23, 3=23, 5=23, 10=23 |
| 04_Cam_Dograma | 92 | 23 | 1=23, 3=23, 5=23, 10=23 |
| 05_Ocak_Arkasi | 76 | 27 | 1=27, 3=27, 5=22 |

## Measured outputs

The experiment records per-reference candidate boxes, score, elapsed time,
target/reference SHA, and checkpoint progress. Candidate count is not accuracy.
A reference crop can point to a wrong object or background; this is why no
automatic acceptance is derived from the scores.

## Independent decision

**NO-GO for production geometry.** The strongest useful next path is a
hybrid abstaining decision: image-guided candidates plus text baseline
agreement, bbox-prompted SAM2, category-specific printable-surface rules,
and human review for disagreement. PETEK must remain contour/slot based,
not forced into a four-corner quad.

## Limitations

- No approved source-SHA ground truth was available.
- Legacy geometry was used only to create candidate reference crops.
- Text-guided and SIFT results remain baselines; their outputs were not relabeled as truth.
- Center-prompt SAM2 masks are not substituted for bbox-prompted masks.

## Coverage blockers

- The completed run has 140 distinct targets: 21 Wi-Fi, 23 Cam Dikey, 23 Cam Yatay,
  23 Ahşap, 23 Cam Doğrama, and 27 Ocak Arkası candidates were available through
  reference crops. PETEK has no verified legacy product crop, so it was not fabricated
  and remains blocked rather than being counted as a successful category.
- Ocak Arkası has only five crop-backed independent references; higher reference counts
  therefore have fewer eligible independent targets. This is a data-coverage limitation,
  not a model success.
- Missing category in this run: 06_PETEK.
