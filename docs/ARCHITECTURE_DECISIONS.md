# PETEK V3 architecture decisions — 2026-10-21

## A. Remove the artificial 13-slot contract
PR #11 procedural slots remain preserved and unmerged for reference. New PETEK V3 keeps each source's original ventilation count, geometry, shadows, top curved opening and lower floor image. No synthesized holes/arches or cloned patches.

## B. Immutable source-coordinate mask
Use one full-scene grayscale mask of printable wood. Project contain-fitted artwork once into reviewed quadrilateral; composite ONLY masked pixels. All mask-zero source pixels must remain exactly the same in the pre-encoded render, measured by array equality. PNG is lossless; JPEG/final 3:4 resize does not preserve literal same encoded bytes and must not be falsely claimed to.

## C. Human review is mandatory
OpenCV light/low-chroma segmentation supplies an editable DRAFT. It can misclassify white floor, dark wood, bevel or reflections. A human reviewer paints protection/wood corrections and approves a source SHA + mask SHA pair. Changed source/hash/geometry rejects render. Optional heavier segmentation needs benchmark, not automatic trust.

## D. Blur correction
PETEK bypasses the legacy scene-wide quality pass, artificial grain and repeated image enlargement. Artwork uses aspect-preserving contain, bounded virtual resolution, single homography and local mask-edge antialias. Marketplace 3:4 uses proportional scene resize and neutral surround without global blur. This protects image detail but cannot invent detail absent from source.

## E. State, commerce, safety
Source templates and legacy ayarlar.db/json remain read-only to new PETEK code. PETEK uses isolated profile DB and batch ledger under LOCALAPPDATA on Windows (away from OneDrive). Batch gives stable internal SKU, append-safe local CSV/XLSX, immutable artifacts and safe resume. Barcode is NOT a GS1/EAN registration. No marketplace posting or auto cloud upload.

## F. One-window UI, no unsafe merge
PETEK Review/Batch tab is registered within existing Flask Template Review Center. Six legacy categories retain their old paths. Existing cloud-first factory run explicitly skips PETEK; its dedicated local-only batch tab is the safe route. PR #9, #11, #12 are NOT blindly merged; new feature branch starts from PR #12 head. Live Windows deployment requires separate approval and actual acceptance.
