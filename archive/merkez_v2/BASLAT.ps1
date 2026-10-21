$ErrorActionPreference = 'Stop'
try {
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONUTF8 = '1'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $options = New-Object System.Collections.ArrayList
    foreach ($p in @('C:\AI_WORK\gorsel-mockup-automation-src\.venv\Scripts\python.exe','C:\AI_WORK\gorsel-mockup-automation-src\venv\Scripts\python.exe')) {
        if (Test-Path -LiteralPath $p) { [void]$options.Add(@{exe=$p;prefix=@()}) }
    }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        foreach ($v in @('-3','-3.11','-3.12','-3.10','-3.13')) { [void]$options.Add(@{exe=$py.Source;prefix=@($v)}) }
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python -and $python.Source -notmatch 'WindowsApps') { [void]$options.Add(@{exe=$python.Source;prefix=@()}) }
    $selected = $null
    $probe = "import importlib.util,sys;sys.exit(0 if sys.version_info>=(3,10) and all(importlib.util.find_spec(x) for x in ['cv2','numpy','PIL','requests','openpyxl','flask','tkinter']) else 2)"
    foreach ($option in $options) {
        $exe = $option.exe
        $prefix = $option.prefix
        try {
            & $exe @prefix -B -c $probe 2>$null
            if ($LASTEXITCODE -eq 0) { $selected=$option; break }
        } catch { continue }
    }
    if (-not $selected) { throw 'Render bagimliliklari olan Python bulunamadi. Otomatik pip kurulumu yapilmadi. Bu mesaji gonderin.' }
    Write-Host ('Python: ' + $selected.exe + ' ' + ($selected.prefix -join ' '))
    $exe = $selected.exe
    $prefix = $selected.prefix
    & $exe @prefix -B (Join-Path $PSScriptRoot 'merkez.py')
    if ($LASTEXITCODE -ne 0) { Write-Host 'DURDU mesajini veya sonuc ZIP dosyasini sohbete gonderin.' }
} catch { Write-Host ('DURDU: ' + $_.Exception.Message) }
