import hashlib, json, os, socket, stat, subprocess
from pathlib import Path


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest().upper()

def run(args, timeout=180, env=None, cwd=None):
    proc = subprocess.run([str(a) for a in args], capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=timeout,
                          env=env, cwd=cwd)
    if proc.returncode:
        raise RuntimeError('Komut basarisiz: ' + str(args[0]) + '\n' + proc.stderr[-1800:])
    return proc.stdout

def idle():
    for port in (8080, 8999):
        for family, address in ((socket.AF_INET, '127.0.0.1'), (socket.AF_INET6, '::1')):
            with socket.socket(family) as sock:
                sock.settimeout(.2)
                if sock.connect_ex((address, port)) == 0:
                    raise RuntimeError('Panel portu acik: ' + str(port))
    script = ("$ErrorActionPreference='Stop'; Get-CimInstance Win32_Process | "
              "Where-Object { $_.ProcessId -ne $PID -and ($_.Name -match '^(python(w)?|py|uvicorn|gunicorn)(\\.exe)?$' "
              "-or ($_.CommandLine -match 'sablon_oto_izleyici|pc_master_factory|SABLON_V2_MIMARI')) } | "
              "Select-Object ProcessId,Name | ConvertTo-Json -Compress")
    out = run(['powershell.exe', '-NoProfile', '-Command', script])
    processes = json.loads(out) if out.strip() else []
    if isinstance(processes, dict):
        processes = [processes]
    bad = [p for p in processes if int(p['ProcessId']) not in (os.getpid(), os.getppid())]
    if bad:
        raise RuntimeError('Ilgili/Python surecleri acik; kapatip yeni calistirma yapin: ' + json.dumps(bad))

def files(root):
    result = []
    def walk_error(err):
        raise err
    for folder, dirs, names in os.walk(root, followlinks=False, onerror=walk_error):
        for name in dirs + names:
            p = Path(folder) / name
            info = p.lstat()
            # OneDrive cloud reparse tags are permitted for authorized reads;
            # junctions and symbolic links are never followed.
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_reparse_tag', 0) in (0xA0000003, 0xA000000C):
                raise RuntimeError('Link/junction bulundu, atlanmadi: ' + str(p))
        for name in names:
            p = Path(folder) / name
            if not p.is_file():
                raise RuntimeError('Normal dosya degil: ' + str(p))
            result.append(p)
    return sorted(result)
