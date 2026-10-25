# Issue #55 Phase 3 summary

- Existing evidence evaluated: **170/170** images.
- Categories: 01_Wifi_Kutusu=21, 02_Cam_Tablo_Dikey=23, 02_Cam_Tablo_Yatay=23, 03_Ahsap_Tablo=23, 04_Cam_Dograma=23, 05_Ocak_Arkasi=27, 06_PETEK=30.
- Methods compared: registration-only, detector-only, detector plus center-prompt mask draft.
- Ground truth: `UNKNOWN_GT`; no precision, recall, IoU, corner accuracy, or wrong-object rate is claimed.
- OWLv2, Grounding DINO, and SAM2.1 had recorded local inference for 170/170; their outputs remain draft candidates.
- Florence-2 was not counted because the recorded Transformers compatibility error blocked inference.
- Selected review evidence: 20 glass cards and 28 category cards in `phase3/visual_review/INDEX.html`.
- Release decision: **NO-GO / REVIEW_REQUIRED**.
