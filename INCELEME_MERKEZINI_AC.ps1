$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppPath = Join-Path $RepoRoot "SABLON_V2_MIMARI\app.py"

function Test-RuntimeRoot([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    return Test-Path -LiteralPath (Join-Path $Path "SABLON_V2_MIMARI\ayarlar.db")
}

$runtime = $env:MOCKUP_RUNTIME_WORKSPACE

if (-not (Test-RuntimeRoot $runtime)) {
    $candidates = @(
        (Join-Path $env:USERPROFILE "OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu"),
        (Join-Path $env:USERPROFILE "OneDrive\Desktop\GörselÜretme-ve-Mockup Otomasyonu"),
        (Join-Path $env:USERPROFILE "Desktop\GörselÜretme-ve-Mockup Otomasyonu")
    )

    $runtime = $null
    foreach ($candidate in $candidates) {
        if (Test-RuntimeRoot $candidate) {
            $runtime = $candidate
            break
        }
    }
}

if (-not (Test-RuntimeRoot $runtime)) {
    $searchRoots = @(
        (Join-Path $env:USERPROFILE "OneDrive"),
        (Join-Path $env:USERPROFILE "Desktop")
    ) | Where-Object { Test-Path -LiteralPath $_ }

    foreach ($searchRoot in $searchRoots) {
        $match = Get-ChildItem -LiteralPath $searchRoot -Filter "ayarlar.db" -File -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Directory.Name -eq "SABLON_V2_MIMARI" } | Select-Object -First 1
        if ($match) {
            $candidate = Split-Path -Parent $match.Directory.FullName
            if (Test-RuntimeRoot $candidate) {
                $runtime = $candidate
                break
            }
        }
    }
}

if (-not (Test-RuntimeRoot $runtime)) {
    Write-Host ""
    Write-Host "HATA: Ana çalışma klasörü otomatik bulunamadı." -ForegroundColor Red
    Write-Host "Beklenen dosya: SABLON_V2_MIMARI\ayarlar.db"
    Write-Host ""
    Read-Host "Kapatmak için Enter"
    exit 2
}

$env:MOCKUP_RUNTIME_WORKSPACE = $runtime

Write-Host "==============================================================================="
Write-Host "                       ŞABLON İNCELEME MERKEZİ"
Write-Host "==============================================================================="
Write-Host ""
Write-Host "Ana çalışma klasörü otomatik bulundu:" -ForegroundColor Green
Write-Host $runtime
Write-Host ""

try {
    $listener = Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) {
        $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)" -ErrorAction SilentlyContinue
        $commandLine = [string]$owner.CommandLine
        if ($commandLine -match "SABLON_V2_MIMARI[\\/]app\.py") {
            Write-Host "Eski İnceleme Merkezi kapatılıyor..." -ForegroundColor Yellow
            Stop-Process -Id $listener.OwningProcess -Force -ErrorAction Stop
            Start-Sleep -Milliseconds 700
        }
        else {
            Write-Host ""
            Write-Host "HATA: 8080 portunu başka bir program kullanıyor." -ForegroundColor Red
            Write-Host "PID: $($listener.OwningProcess)"
            Read-Host "Kapatmak için Enter"
            exit 3
        }
    }
}
catch {
    Write-Host "Port kontrolü atlandı: $($_.Exception.Message)" -ForegroundColor Yellow
}

if (-not (Test-Path -LiteralPath $AppPath)) {
    Write-Host "HATA: app.py bulunamadı: $AppPath" -ForegroundColor Red
    Read-Host "Kapatmak için Enter"
    exit 4
}

Write-Host "İnceleme Merkezi başlatılıyor..." -ForegroundColor Cyan
$process = Start-Process -FilePath "python" -ArgumentList @("`"$AppPath`"") -WorkingDirectory $RepoRoot -PassThru -NoNewWindow

$url = "http://127.0.0.1:8080/"
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    if ($process.HasExited) { break }
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 1
        if ($response.StatusCode -eq 200) {
            $ready = $true
            break
        }
    }
    catch {
        Start-Sleep -Milliseconds 250
    }
}

if ($ready) {
    Write-Host "Hazır. Tarayıcı açılıyor..." -ForegroundColor Green
    Start-Process $url
}
else {
    Write-Host ""
    Write-Host "HATA: İnceleme Merkezi zamanında açılamadı." -ForegroundColor Red
    if ($process.HasExited) { Write-Host "Python çıkış kodu: $($process.ExitCode)" }
}

if (-not $process.HasExited) {
    Wait-Process -Id $process.Id
}