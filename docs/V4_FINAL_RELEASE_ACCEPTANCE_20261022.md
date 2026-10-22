# V4.0 Windows Final Release — Evidence and GO/NO-GO Matrix

**Status snapshot (2026-10-22): OPEN. This is an acceptance tracker, not a claim of completed production testing.**

| Gate | Work | Baseline | Final evidence required | Status |
| --- | --- | --- | --- | --- |
| G0 | Canonical private V3.14 Tk + PR source reconciliation | V3.14 user ZIP, PR9/12/13/14/26/27/28 separate | Exact code SHA, version/feature map, portable source build | BLOCKED: integration |
| G1 | Old six-category geometry + editor | Flask app and /tools bridged in V3.14 | Native Windows opening with actual workspace and verified backup; manual 4-corner save/load | PENDING |
| G2 | Old independent professional tools | PR12 bundled legacy tools | Every tool launched on Windows using non-customer fixture | PENDING |
| G3 | Seven category dynamic approved template discovery | 10 pinned Daily templates | All currently approved eligible templates dynamically available, zero silent auto approval | BLOCKED: code |
| G4 | Durable single factory | PETEK and six-category separate jobs | Shared queue, 1000 items synthetic, progress/stop/resume + source/SKU/Excel/output parity | BLOCKED: code |
| G5 | Immutable output/security | Existing PETEK SHA receipts / PR27 | Real multi-process Windows crash + naming/extension collision tests, zero source overwrite | PENDING |
| G6 | PETEK mask + panel realism | Private V3.11 tools and V3.8 natural lighting | Real curves/vent/pinhole/quad clip/A-B QA; unchanged outside-mask pixels | PENDING |
| G7 | Six-category product visual quality | Historical approved sample templates | Minimum one human approved template for each of 6 + 2 artwork outputs, occlusion check | PENDING |
| G8 | Workspace and database safety | Read-only preflight and backup-on-editor-open | Consistent backup SHA/integrity/rowcount + restore drill, rollback, Unicode paths | PENDING |
| G9 | One-click deploy | V3.14 BAT/venv | Clean Windows install, pinned dependencies, verify no hardcoded historical backup requirement | PENDING |
| G10 | Release acceptance | V3.14 synthetic Linux/Xvfb 90/90 reported | Windows real-user accepted output, run logs, ZIP SHA, release notes, no unmet P0 | NO-GO |

## Seven-category minimum human QA fixture matrix
- 01_Wifi_Kutusu: correct 40x30 external dimensions, 12cm **internal** depth; old manual approval and occlusion protected.
- 02_Cam_Tablo_Dikey: 60x90 portrait, source edge preserved.
- 02_Cam_Tablo_Yatay: 60x90 landscape, right perspective.
- 03_Ahsap_Tablo: 50x70 portrait and unchanged frame.
- 04_Cam_Dograma: 25x35 actual tabletop/counter angle, verified foreground occlusion or explicitly BLOCKED.
- 05_Ocak_Arkasi: actual stove-top scene, glass correctly segmented, black source fails closed.
- PETEK_DOLABI: genuine slits count varies, separately manually drawn top/bottom curves, full artwork coverage only on wood, photo-native shadow/light/vent.

Each row requires source SHA, prior approved mask profile UID+SHA, artifact key/recipe, original pixel protection test, generated PNG+size (typically 1200x1600), local SKU/CSV/XLSX receipt, manual human visual QA, exact original backup receipt.

## No-go triggers
1. Original source, approved mask or historical SKU overwritten, deleted, silently renamed, or migrated without separate user approval.
2. Wrong source mapping due to same name different hash or extension normalization, wrong category/aspect, or loss of old review tools.
3. PR branch tests passing while actual user's Windows install/batch/DB never tested (report as pending, not successful).
4. Legacy camera/mask foreground requirements bypassed, or PETEK slots filled by false morphological cleanup.
5. 7-category single-batch promised but only pinned ten templates actually selectable.
6. Cloud marketplace upload or access to personal photos performed by default.

## Required final signoff report format
- Canonical PR + commit SHA + source/release ZIP SHA256 + build recipe and pinned dependencies.
- Table per issue #29–#35: DONE/IN PROGRESS/FAIL/BLOCKED, code files, CI result, Windows proof, next concrete command.
- Native Windows acceptance screenshots/log only in private channel/workspace, not public GitHub when they contain photos, paths or secrets.
- User signoff with opt-in activation and verified restore path; no silent merger of PR drafts.