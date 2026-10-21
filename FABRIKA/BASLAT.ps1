param([switch]$Test)
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
Set-Location (Split-Path -Parent $PSScriptRoot)
$options = New-Object System.Collections.ArrayList
foreach ($candidate in @('.venv\Scripts\python.exe','C:\AI_WORK\gorsel-mockup-automation-src\.venv\Scripts\python.exe','C:\AI_WORK\gorsel-mockup-automation-src\venv\Scripts\python.exe')) {
    if (Test-Path -LiteralPath $candidate) { [void]$options.Add(@{exe=(Resolve-Path $candidate).Path;prefix=@()}) }
}
$py = Get-Command py.exe -ErrorAction SilentlyContinue
if ($py) { foreach ($version in @('-3.11','-3.12','-3.13','-3')) { [void]$options.Add(@{exe=$py.Source;prefix=@($version)}) } }
$python = Get-Command python.exe -ErrorAction SilentlyContinue
if ($python -and $python.Source -notmatch 'WindowsApps') { [void]$options.Add(@{exe=$python.Source;prefix=@()}) }
$probe = "import cv2,numpy,PIL,openpyxl,flask,requests,tkinter,sys;sys.exit(0 if sys.version_info>=(3,10) else 2)"
$chosen = $null
foreach ($option in $options) {
    try { $exe=$option.exe; $prefix=$option.prefix; & $exe @prefix -B -c $probe 2>$null; if ($LASTEXITCODE -eq 0) {$chosen=$option;break} } catch { continue }
}
if (-not $chosen) { Write-Host 'Gerekli bagimliliklari olan Python bulunamadi. requirements-core.lock.txt ve WINDOWS_RELEASE_STATUS.md dosyalarini kontrol edin.'; exit 2 }
$exe=$chosen.exe; $prefix=$chosen.prefix
if ($Test) {
    & $exe @prefix -B -m unittest tests.test_factory_v3 -v
} else {
    & $exe @prefix -B -m FABRIKA.app
}
exit $LASTEXITCODE
