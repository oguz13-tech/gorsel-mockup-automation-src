# Independent technical recommendation — Issue #55

## BENİM TEKNİK KARARIM

Use a **hybrid abstaining pipeline (C)**, but only as a review-candidate
generator. Registration-only is useful when the same product is visibly repeated,
yet the previous T1 count is not product accuracy. Detector-only produces useful
candidate boxes, but OWLv2 and Grounding DINO disagreement is common evidence of
ambiguity, not a reason to choose one box. Center-prompt SAM2 is not product
segmentation.

| Category | Recommendation | Confidence | Reason |
|---|---|---:|---|
| Cam Dikey/Yatay | C: detector consensus + glass edge/reflection rules + abstain | Medium-low | Transparent surfaces and background panels are easy false positives. |
| Cam Doğrama | C with horizontal/vertical physical priors | Medium-low | Frame and glass plane must be separated. |
| Ocak Arkası | C with panel-vs-tile/hood exclusions | Medium-low | Text prompts can select surrounding tile or cabinet. |
| Wi-Fi Kutusu | C plus printable MDF-cover prior | Medium | Whole-box localization is not printable-surface localization. |
| Ahşap Tablo | C plus inner-surface/frame separation | Medium | Outer frame must not become printable area. |
| PETEK | D: mask/contour/slot specialist, never forced into a quad | Low | Curvature and ventilation openings need a different geometry representation. |

## KATILMADIĞIM NOKTALAR

- A T1/SIFT inlier count is not a product match without product-ROI evidence.
- A detector confidence or detector agreement is not accuracy without approved
  ground truth.
- A center-positive SAM mask must not be treated as an instance mask.
- A four-corner abstraction is technically wrong for PETEK curvature and slots.
- Running another heavy model over all 170 images without a predeclared metric
  would add output volume, not evidence.

## EN DEĞERLİ SONRAKİ DENEY

Create a small human-labeled holdout: three easy, three hard, and three negative
examples per category. Record source SHA, target-present state, product bbox,
printable-surface mask, and PETEK contour/slots. Compare registration-only,
detector-consensus, and hybrid abstention using predeclared wrong-object and
review-required thresholds. Do not promote geometry unless the human-reviewed
holdout passes.

## BUGÜN ÜRETİME ALINABİLİR Mİ?

**NO-GO.** The current 170-row evidence has no approved ground truth, and the
SAM masks use center prompts. The outputs are valuable for selecting human review
cards and designing the next labeled experiment, not for automatic production
geometry or approval.
