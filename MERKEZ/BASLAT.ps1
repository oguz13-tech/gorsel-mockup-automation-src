$ErrorActionPreference = 'Stop'
try {
  Set-Location -LiteralPath $PSScriptRoot
  $env:PYTHONUTF8 = '1'
  $env:PYTHONDONTWRITEBYTECODE = '1'
  $local = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
  if (Test-Path -LiteralPath $local) {
    & $local -B (Join-Path $PSScriptRoot 'merkez.py')
  } else {
    & py -3 -B (Join-Path $PSScriptRoot 'merkez.py')
  }
  if ($LASTEXITCODE -ne 0) { Write-Host 'DURDU: Hata olustu. Kurulum ve on-kontrol mesajlarini inceleyin.' }
} catch { Write-Host ('DURDU: ' + $_.Exception.Message) }
