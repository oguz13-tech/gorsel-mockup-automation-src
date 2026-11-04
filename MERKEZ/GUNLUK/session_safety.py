"""Pinned installed code and session-only write boundaries."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import urllib.parse

FACTORY='99_SISTEM_MOTORLARI_VE_KODLAR/SISTEM_MOTORU/pc_master_factory.py'
FILL_SHA='123785ea3ab3ff16d780eaebf3d4a76279716a74972b768c8b9b5a1ca55f802c'
ART_SHA='22843099df02cc6e84c7fdb7daad11a1ac89c90f32bd4b97b4ffffb441e2d9eb'

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()

def inside(path,root):
    path,root=Path(path).resolve(),Path(root).resolve()
    return path==root or root in path.parents

def atomic_json(path,value):
    import uuid
    path=Path(path);temp=path.with_name('.'+uuid.uuid4().hex+'.json-tmp')
    try:
        with temp.open('xb') as f:
            f.write(json.dumps(value,ensure_ascii=False,indent=2).encode());f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:temp.unlink(missing_ok=True)

def db_file(value):
    value=os.fsdecode(value)
    if value.startswith('file:'):
        value=urllib.parse.unquote(urllib.parse.urlsplit(value).path)
        if os.name=='nt' and len(value)>2 and value[0]=='/' and value[2]==':':value=value[1:]
    return Path(value).resolve()

def readonly_connections(live_db):
    """All SQLite access in the viewing process is forced to one mode=ro DB."""
    original=sqlite3.connect;expected=Path(live_db).resolve()
    def connect(database,*args,**kwargs):
        if db_file(database)!=expected:raise PermissionError('PANEL_OTHER_DATABASE_BLOCKED')
        if args:raise PermissionError('PANEL_UNEXPECTED_SQLITE_ARGUMENTS')
        kwargs['uri']=True
        conn=original(expected.as_uri()+'?mode=ro',**kwargs)
        conn.execute('PRAGMA query_only=ON')
        return conn
    sqlite3.connect=connect
    return original

def install_write_boundary(temp,output,*,live_db=None,listen_port=None):
    roots=(Path(temp).resolve(),Path(output).resolve())
    expected_db=Path(live_db).resolve() if live_db else None
    def allowed(p):
        if p is None or isinstance(p,int):return True
        return any(inside(os.fsdecode(p),r) for r in roots)
    def audit(event,args):
        if event=='open':
            if args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND) and not allowed(args[0]):raise PermissionError('SESSION_WRITE_OUTSIDE_OUTPUT:'+str(args[0]))
        elif event=='os.mkdir':
            if not allowed(args[0]) and not Path(args[0]).is_dir():raise PermissionError('SESSION_MKDIR_OUTSIDE_OUTPUT')
        elif event in ('os.remove','os.rmdir','os.truncate','os.chmod','os.utime'):
            if not allowed(args[0]):raise PermissionError('SESSION_MUTATION_OUTSIDE_OUTPUT')
        elif event in ('os.rename','os.link','os.symlink'):
            if not allowed(args[0]) or not allowed(args[1]):raise PermissionError('SESSION_MOVE_OUTSIDE_OUTPUT')
        elif event=='sqlite3.connect':
            value=str(args[0]);path=db_file(value)
            if any(inside(path,r) for r in roots):return
            if expected_db and path==expected_db and value.startswith('file:') and urllib.parse.parse_qs(urllib.parse.urlsplit(value).query).get('mode')==['ro']:return
            raise PermissionError('SESSION_SQLITE_OUTSIDE_COPY_OR_READONLY_VIEW')
        elif event in ('subprocess.Popen','os.system','socket.connect'):
            raise PermissionError('SESSION_EXTERNAL_PROCESS_OR_NETWORK_BLOCKED')
        elif event=='socket.bind':
            if listen_port is None or args[1] != ('127.0.0.1',listen_port):raise PermissionError('SESSION_UNEXPECTED_LISTENER')
        elif event=='socket.getaddrinfo':
            if listen_port is None or args[0] not in ('127.0.0.1','localhost') or args[1]!=listen_port:raise PermissionError('SESSION_NETWORK_LOOKUP_BLOCKED')
    sys.dont_write_bytecode=True;sys.addaudithook(audit)

def verify_installed(code,source,tree,spec,checks):
    overlay={r['path']:r['after_sha256'] for r in spec['files']}
    count=0
    for rel,(mode,kind,oid) in tree.items():
        if not checks.operational(rel):continue
        if kind!='blob' or mode not in ('100644','100755'):raise RuntimeError('NON_REGULAR_CODE:'+rel)
        src,dst=source/rel,code/rel;checks.no_redirect(src);checks.no_redirect(dst)
        raw=src.read_bytes()
        if checks.blob(raw)!=oid and checks.blob(raw.replace(b'\r\n',b'\n'))!=oid:raise RuntimeError('PR9_SOURCE_BLOB_CHANGED:'+rel)
        if rel==FACTORY:
            if digest(dst) not in (FILL_SHA,'a68dc895d84ee918062911f7169f6ea30ff8956dc6279e0951755ccaa617be9e'):raise RuntimeError('FILL_V1_CHANGED')
        elif rel in overlay:
            if digest(dst)!=overlay[rel]:raise RuntimeError('NUMBER_GUARD_V2_CHANGED:'+rel)
        elif dst.read_bytes().replace(b'\r\n',b'\n')!=raw.replace(b'\r\n',b'\n'):raise RuntimeError('UNEXPECTED_CODE_CHANGE:'+rel)
        count+=1
    for rel,expected in overlay.items():
        p=code/rel;checks.no_redirect(p)
        if digest(p)!=expected:raise RuntimeError('OVERLAY_MISSING:'+rel)
    return count+sum(rel not in tree for rel in overlay)
