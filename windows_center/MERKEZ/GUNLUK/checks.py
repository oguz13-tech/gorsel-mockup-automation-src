import hashlib, os
from pathlib import Path, PurePosixPath
from helpers import run
COMMIT="37831c73eaf04cc729628ea5cff3ba45bb9d44df"

def no_redirect(p):
    for part in (p, *p.parents):
        if part.exists():
            st = part.lstat()
            if part.is_symlink() or getattr(st, 'st_reparse_tag', 0) in (0xA0000003, 0xA000000C):
                raise RuntimeError('Symlink/junction yolu engellendi: ' + str(part))

def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\x00' + data).hexdigest()

def git(code, *args):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0')
    return run(['git', '--no-optional-locks', '-C', code, '-c', 'core.fsmonitor=false', *args], env=env)

def valid_code_path(rel):
    p = PurePosixPath(rel)
    if p.is_absolute() or '..' in p.parts or '\\' in rel or ':' in rel:
        return False
    if any(part.casefold() in ('.git', '2_sablon_havuzu', '2_sablon_havuzu_orijinal_yedek') for part in p.parts):
        return False
    return p.suffix.lower() in ('.py', '.bat', '.ps1', '.js', '.html')

def source_tree(source):
    tree = {}
    for entry in git(source, 'ls-tree', '-rz', COMMIT).split('\x00'):
        if not entry:
            continue
        meta, rel = entry.split('\t', 1)
        mode, kind, oid = meta.split(' ')
        tree[rel] = (mode, kind, oid)
    return tree

def source_verify(source, paths, tree):
    for rel in paths:
        if not valid_code_path(rel):
            raise RuntimeError('Kod disi/guvensiz kurulum yolu: ' + rel)
        if rel not in tree or tree[rel][0] not in ('100644', '100755') or tree[rel][1] != 'blob':
            raise RuntimeError('PR9 kaynak agacinda normal kod dosyasi degil: ' + rel)
        p = source/rel
        no_redirect(p)
        if not p.is_file() or blob(p.read_bytes()) != tree[rel][2]:
            raise RuntimeError('Kaynak PR9 blob ile ayni degil: ' + rel)
        if p.suffix.lower() == '.py':
            compile(p.read_bytes(), str(p), 'exec')

def operational(rel):
    p = PurePosixPath(rel)
    if p.parts[0] in ('.github', 'tests', 'docs', '.vscode'):
        return False
    return p.suffix.lower() in ('.py','.bat','.ps1','.js','.html','.css') or p.name.startswith('requirements')

def verify_unchanged_dependencies(source, code, paths, tree):
    count = 0
    for rel, (mode, kind, oid) in tree.items():
        if rel in paths or not operational(rel):
            continue
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise RuntimeError('Kaynak bagimliligi normal dosya degil: ' + rel)
        src, dst = source/rel, code/rel
        no_redirect(src); no_redirect(dst)
        if not dst.is_file() or not src.is_file() or blob(src.read_bytes()) != oid:
            raise RuntimeError('Kapsam disi bagimlilik eksik/bozuk: ' + rel)
        if src.read_bytes().replace(b'\r\n', b'\n') != dst.read_bytes().replace(b'\r\n', b'\n'):
            raise RuntimeError('Kapsam disi bagimlilik PR9 ile farkli; kurulum yapilmadi: ' + rel)
        count += 1
    return count
