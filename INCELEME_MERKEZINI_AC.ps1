param([string]$OpenPath = "/")
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppPath = Join-Path $RepoRoot "SABLON_V2_MIMARI\app.py"
$WatcherPath = Join-Path $RepoRoot "99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\sablon_oto_izleyici.py"

function Test-RuntimeRoot([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    return Test-Path -LiteralPath (Join-Path $Path "SABLON_V2_MIMARI\ayarlar.db")
}

$runtime = $env:MOCKUP_RUNTIME_WORKSPACE
$runtimeSource = "environment"

if (-not (Test-RuntimeRoot $runtime)) {
    $pointerBase = $env:LOCALAPPDATA
    if ([string]::IsNullOrWhiteSpace($pointerBase)) {
        $pointerBase = Join-Path $env:USERPROFILE ".jarvis_mockup"
    }
    $pointerPath = Join-Path $pointerBase "JarvisMockup\runtime_workspace.txt"
    if (Test-Path -LiteralPath $pointerPath) {
        try {
            $pointerRuntime = (Get-Content -LiteralPath $pointerPath -Raw -Encoding UTF8).Trim()
            if (Test-RuntimeRoot $pointerRuntime) {
                $runtime = $pointerRuntime
                $runtimeSource = "runtime pointer"
            }
        } catch {
            Write-Host "Runtime pointer okuma uyarisi: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
}

if (-not (Test-RuntimeRoot $runtime)) {
    $runtimeSource = "automatic discovery"
    $candidates = @(
        (Join-Path $env:USERPROFILE "OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu"),
        (Join-Path $env:USERPROFILE "OneDrive\Desktop\GörselÜretme-ve-Mockup Otomasyonu"),
        (Join-Path $env:USERPROFILE "Desktop\GörselÜretme-ve-Mockup Otomasyonu")
    )
    $runtime = $null
    foreach ($candidate in $candidates) {
        if (Test-RuntimeRoot $candidate) { $runtime = $candidate; break }
    }
}

if (-not (Test-RuntimeRoot $runtime)) {
    $roots = @((Join-Path $env:USERPROFILE "OneDrive"), (Join-Path $env:USERPROFILE "Desktop"))
    foreach ($searchRoot in $roots) {
        if (-not (Test-Path -LiteralPath $searchRoot)) { continue }
        $match = Get-ChildItem -LiteralPath $searchRoot -Filter "ayarlar.db" -File -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Directory.Name -eq "SABLON_V2_MIMARI" } | Select-Object -First 1
        if ($match) {
            $candidate = Split-Path -Parent $match.Directory.FullName
            if (Test-RuntimeRoot $candidate) { $runtime = $candidate; break }
        }
    }
}

if (-not (Test-RuntimeRoot $runtime)) {
    Write-Host ""
    Write-Host "HATA: Ana çalışma klasörü otomatik bulunamadı." -ForegroundColor Red
    Write-Host "Beklenen dosya: SABLON_V2_MIMARI\ayarlar.db"
    Read-Host "Kapatmak için Enter"
    exit 2
}

$env:MOCKUP_RUNTIME_WORKSPACE = $runtime
$env:MOCKUP_NO_AUTO_BROWSER = "1"

Write-Host "Ana çalışma klasörü bulundu:" -ForegroundColor Green
Write-Host $runtime
Write-Host "Runtime kaynağı: $runtimeSource" -ForegroundColor DarkGray

# Safety: Opening UI must not silently write a new runtime baseline.
# The separate explicit maintenance script may create one only after review.
Write-Host "P0: Runtime AI baseline otomatik olusturulmuyor (salt-okunur baslangic)." -ForegroundColor DarkYellow

if (-not (Test-Path -LiteralPath $WatcherPath)) {
    Write-Host "HATA: Şablon izleyici bulunamadı: $WatcherPath" -ForegroundColor Red
    Read-Host "Kapatmak için Enter"
    exit 6
}

# P0 safety: opening the review UI must never start, restart or stop a watcher.
Write-Host "P0 GUVENLIK: Otomatik watcher BASLATILMADI." -ForegroundColor Yellow

try {
    $listener = Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) {
        $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)" -ErrorAction SilentlyContinue
        $cmd = [string]$owner.CommandLine
        if ($cmd -match "SABLON_V2_MIMARI[\\/]app\.py") {
            Write-Host "Eski İnceleme Merkezi kapatılıyor..." -ForegroundColor Yellow
            Stop-Process -Id $listener.OwningProcess -Force -ErrorAction Stop
            Start-Sleep -Milliseconds 700
        } else {
            Write-Host "HATA: 8080 portunu başka bir program kullanıyor. PID: $($listener.OwningProcess)" -ForegroundColor Red
            Read-Host "Kapatmak için Enter"
            exit 3
        }
    }
} catch {
    Write-Host "Port kontrol uyarısı: $($_.Exception.Message)" -ForegroundColor Yellow
}

if (-not (Test-Path -LiteralPath $AppPath)) {
    Write-Host "HATA: app.py bulunamadı: $AppPath" -ForegroundColor Red
    Read-Host "Kapatmak için Enter"
    exit 4
}

Write-Host "Merkez başlatılıyor..." -ForegroundColor Cyan
$process = Start-Process -FilePath "python" -ArgumentList @($AppPath) -WorkingDirectory $RepoRoot -PassThru
$url = "http://127.0.0.1:8080" + $OpenPath
$ready = $false
for ($i = 0; $i -lt 50; $i++) {
    if ($process.HasExited) { break }
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8080/" -TimeoutSec 1
        if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch {
        Start-Sleep -Milliseconds 250
    }
}

if ($ready) {
    Write-Host "Hazır. Tarayıcı açılıyor: $url" -ForegroundColor Green
    Start-Process $url
    exit 0
}

Write-Host "HATA: Merkez zamanında açılamadı." -ForegroundColor Red
if ($process.HasExited) { Write-Host "Python çıkış kodu: $($process.ExitCode)" }
Read-Host "Kapatmak için Enter"
exit 5
