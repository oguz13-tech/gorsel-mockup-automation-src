# Görsel Üretim Merkezi — Windows delivery

1. Copy the package to a writable Windows folder.
2. Run `KURULUM.bat` once with Python 3.11 or 3.12.
3. Run `BASLAT.bat`.
4. Before production, create a dated runtime backup and keep the generated
   SHA256 manifest.

This package contains code and tests only; live user data is not bundled.
Production status is never inferred from a preview. PETEK source/mask safety
failures block only the affected template and do not authorize a forced render.

See `docs/WINDOWS_DELIVERY_ACCEPTANCE_20261101.md` for the acceptance boundary.
