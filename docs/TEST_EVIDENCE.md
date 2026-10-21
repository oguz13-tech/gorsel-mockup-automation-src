# PETEK V3 QA evidence

At coding stage: tests have been authored but do NOT count as passed until run.
Primary suite: tests/test_petek_v3.py (synthetic photos / source masks / QA / batch / API).
Legacy tests: tests/test_number_guard_v2.py; tests/test_fill_v1_delivery.py and full repository suite.

Final planned commands:
python -m pip install -r requirements-petek-v3.txt
python -m compileall -q SABLON_V2_MIMARI/core scripts/petek_v3_windows_launcher.py scripts/petek_v3_windows_release.py
python -m pytest -q tests/test_petek_v3.py
python -m pytest -q tests/test_number_guard_v2.py tests/test_fill_v1_delivery.py
python scripts/petek_v3_windows_release.py build --destination dist
python scripts/petek_v3_windows_release.py inspect <zip>

Record OS, commit SHA, actual counts/failures, CI URLs and screenshots AFTER execution. Passing synthetic pixel checks is not the same as approved real mockup appearance or safe Windows live installation.
