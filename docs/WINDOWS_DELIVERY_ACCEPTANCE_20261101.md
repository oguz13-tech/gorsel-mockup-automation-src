# Windows delivery acceptance

## Stable production mode

The normal launcher uses `MERKEZ/BASLAT.bat`. PETEK remains on the source-linked
guarded render path with approved masks and `slot_mode` controls. Experimental
G3/Y3/L1 assets and the single-vertical-shadow preset are not enabled by
default and are not production approval.

## Categories

The six legacy categories remain independently selectable in
`MERKEZ/URETIM_V4/unified_batch.py`:

- `01_Wifi_Kutusu`
- `02_Cam_Tablo_Dikey`
- `02_Cam_Tablo_Yatay`
- `03_Ahsap_Tablo`
- `04_Cam_Dograma`
- `05_Ocak_Arkasi`

No live Windows production run was claimed unless its output and manifest were
actually observed. A category without a real run is reported as
`WINDOWS_NOT_VERIFIED`.

## PETEK safety

Templates with a failed physical/source guard must be skipped, not forced or
automatically approved. The package does not write live SQLite, masks, profiles,
store assignments, approval records, or production history.

## Backup and rollback

Before production, create a dated copy of the live SQLite, store profile,
PETEK profiles, and PETEK masks. Restore only with the application stopped and
after verifying the backup SHA256 manifest.
