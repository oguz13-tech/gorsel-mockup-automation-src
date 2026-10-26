"""Check candidate pins without touching the data workspace."""
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
import sys

def check():
    errors=[]
    for line in (Path(__file__).resolve().parents[1]/'MERKEZ/requirements-v46-lock.txt').read_text().splitlines():
        if not line or line.startswith('#'):continue
        name,expected=line.split('==')
        try:actual=version(name)
        except PackageNotFoundError:actual='MISSING'
        if actual!=expected:errors.append(f'{name}: {actual} (expected {expected})')
    return errors
if __name__=='__main__':
    errors=check();print('\n'.join(errors) if errors else 'Candidate dependencies OK')
    sys.exit(bool(errors))
