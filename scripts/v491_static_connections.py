"""Read-only UI callback/asset/launcher sanity check for the V4.9.1 package."""
from __future__ import annotations
import ast
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
problems=[]


def check_dashboard():
    base=ROOT/'MERKEZ'
    dashboard=ast.parse((base/'premium_dashboard_v489.py').read_text('utf-8'))
    main=ast.parse((base/'merkez.py').read_text('utf-8'))
    methods={node.name for node in ast.walk(main) if isinstance(node,ast.FunctionDef)}
    writes={node.attr for node in ast.walk(dashboard) if isinstance(node,ast.Attribute)
            and isinstance(node.value,ast.Name) and node.value.id=='app'
            and isinstance(node.ctx,ast.Store)}
    reads={node.attr for node in ast.walk(dashboard) if isinstance(node,ast.Attribute)
            and isinstance(node.value,ast.Name) and node.value.id=='app'
            and isinstance(node.ctx,ast.Load)}
    missing=reads-methods-writes-{'root','runtime'}
    if missing:
        problems.append('Undefined dashboard callback/attribute: '+', '.join(sorted(missing)))
    return len(reads)


def check_web():
    html=ROOT/'SABLON_V2_MIMARI/templates'
    static=ROOT/'SABLON_V2_MIMARI/static'
    js='\n'.join(x.read_text('utf-8') for x in static.rglob('*.js'))
    total=0
    for path in html.glob('*.html'):
        source=path.read_text('utf-8')
        for url in re.findall(r'(?:src|href)\s*=\s*[\'\"](/static/[^\'\"?]+)',source):
            if not (ROOT/'SABLON_V2_MIMARI'/url.lstrip('/')).is_file():
                problems.append(f'{path.name}: asset not found {url}')
        callbacks=re.findall(r'onclick\s*=\s*\"([^\"]+)\"',source)
        total+=len(callbacks)
        for arg in callbacks:
            for name in re.findall(r'\b([a-zA-Z_$][\w$]*)\s*\(',arg):
                if name in {'alert','confirm','prompt','getElementById'}:
                    continue
                if not re.search(r'\b(?:function|async function)\s+'+re.escape(name)+r'\b',source+'\n'+js) and not re.search(r'\b(?:const|let|var)\s+'+re.escape(name)+r'\b',source+'\n'+js) and not re.search(r'window\.'+re.escape(name)+r'\b',source+'\n'+js):
                    problems.append(f'{path.name}: missing onclick callback {name}')
    return total


def check_tools():
    app=ast.parse((ROOT/'SABLON_V2_MIMARI/app.py').read_text('utf-8'))
    runner=ast.parse((ROOT/'SABLON_V2_MIMARI/tools_runner.py').read_text('utf-8'))
    allowed=set()
    impl=set()
    for n in ast.walk(app):
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_ALLOWED_USER_TOOLS' for t in n.targets):
            allowed={v.value for v in n.value.elts if isinstance(v,ast.Constant)}
    for n in ast.walk(runner):
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TOOLS' for t in n.targets):
            impl={k.value for k in n.value.keys if isinstance(k,ast.Constant)}
    tools=(ROOT/'SABLON_V2_MIMARI/templates/tools.html').read_text('utf-8')
    buttons=set(re.findall(r"launchTool\('([\w_]+)'",tools))
    if allowed != impl or buttons != impl:
        problems.append(f'Tool maps mismatch: allowed-only={allowed-impl}; implemented-only={impl-allowed}; buttons diff={buttons ^ impl}')
    return len(buttons)


def check_release():
    for filename in ('BASLAT_V46_WINDOWS.bat','BASLAT_V47_WINDOWS.bat','V491_DOGRULA_WINDOWS.bat',
                     'ESKI_GORUNUME_DON_WINDOWS.bat','MAGENTA_TOPLU_GUVENLI_DEGISTIR_WINDOWS.bat',
                     'SABLON_V2_MIMARI/orientation_sort_v489.py', 'SABLON_V2_MIMARI/tools_runner.py'):
        if not (ROOT/filename).is_file():
            problems.append('Required launcher or code not found: '+filename)
    if list(ROOT.rglob('ayarlar.db')):
        problems.append('Personal SQLite DB embedded in distribution')
    if (ROOT/'MERKEZ/.venv').exists():
        problems.append('Vendor-specific preinstalled Python virtual environment embedded')
    return True


def main():
    n=check_dashboard()
    h=check_web()
    t=check_tools()
    check_release()
    print(f'Dashboard refs: {n}; HTML callbacks: {h}; connected tools: {t}; errors: {len(problems)}')
    for entry in problems[:100]:
        print('ERROR:',entry)
    return 0 if not problems else 1

if __name__=='__main__':
    sys.exit(main())
