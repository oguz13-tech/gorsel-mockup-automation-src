"""Cross-platform test selection: Windows cmd does NOT expand *.py globs."""
from pathlib import Path
import sys
import pytest

if __name__ == '__main__':
    project = Path(__file__).resolve().parents[1]
    matches = sorted((project/'tests').glob('test_vnext_petek_*.py'))
    matches += [project/'tests/test_final_petek_contract_20261101.py',
                project/'tests/test_v492_petek_finish_filter.py']
    if not matches or not all(path.is_file() for path in matches):
        raise SystemExit('V4.11.1 PETEK test set incomplete')
    sys.exit(pytest.main(['-q', *(str(p) for p in matches)]))
