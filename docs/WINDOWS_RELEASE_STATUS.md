# Windows PETEK V3 candidate release

Status: SOURCE CANDIDATE; REAL WINDOWS LIVE ACCEPTANCE NOT YET VERIFIED.

Build: python scripts/petek_v3_windows_release.py build --destination dist
Verify ZIP: python scripts/petek_v3_windows_release.py inspect <candidate.zip>
The release builder packages only tracked allowlisted source/GUI files. It excludes private source images, masks, SQLite files, user backups, credentials and unrelated runtime contents.

Extract to a NEW local folder, NOT over the installed Windows application. Launch START_PETEK_V3_WINDOWS.bat. Select the existing runtime workspace from folder picker. The launcher performs a SQLite read-only check, then imports the main localhost Flask app in staging mode without legacy startup migrations/backfill. Browser PETEK tab supports draft masks, paint, human approval and local-only batch.

On Windows, PETEK's private SQLite and outputs default to LOCALAPPDATA/GorselMockup/PetekV3_<workspace hash>, not OneDrive. Source templates remain unmodified. Local CSV/XLSX files are exported there.

Explicit user approval is needed before altering installed code, merging PR, running legacy live migration or posting to marketplaces. Current package is NOT an EXE and is NOT automatically installed.

Still outstanding: actual Windows user acceptance, varied real PETEK visual review, installed Günlük V2 hash compatibility, complete six-category commercial chain, real product image QA and optional registered seller barcodes.
