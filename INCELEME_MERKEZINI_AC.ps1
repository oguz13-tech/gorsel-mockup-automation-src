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

$baselineScript = Join-Path $RepoRoot "scripts\\capture_runtime_baseline.py"
if (Test-Path -LiteralPath $baselineScript) {
    try {
        & python $baselineScript --ensure
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Runtime sürüm baseline oluşturma uyarısı. Çıkış kodu: $LASTEXITCODE" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "Runtime sürüm baseline uyarısı: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

if (-not (Test-Path -LiteralPath $WatcherPath)) {
    Write-Host "HATA: Şablon izleyici bulunamadı: $WatcherPath" -ForegroundColor Red
    Read-Host "Kapatmak için Enter"
    exit 6
}

# İnceleme Merkezi ile staging watcher tek bir çalışma setidir.
# Eski watcher süreçlerini kapatıp aynı runtime ortamıyla temiz bir watcher başlat.
try {
    $watcherPattern = [regex]::Escape($WatcherPath)
    $oldWatchers = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine -match "sablon_oto_izleyici\.py" -and
            $_.CommandLine -match $watcherPattern
        }

    foreach ($oldWatcher in $oldWatchers) {
        Write-Host "Eski şablon izleyici kapatılıyor... PID: $($oldWatcher.ProcessId)" -ForegroundColor Yellow
        Stop-Process -Id $oldWatcher.ProcessId -Force -ErrorAction SilentlyContinue
    }
    if ($oldWatchers) {
        Start-Sleep -Milliseconds 500
    }
} catch {
    Write-Host "Watcher süreç kontrol uyarısı: $($_.Exception.Message)" -ForegroundColor Yellow
}

$watcherLogDir = Join-Path $runtime "99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\logs"
New-Item -ItemType Directory -Force -Path $watcherLogDir | Out-Null
$watcherOut = Join-Path $watcherLogDir "staging_watcher_stdout.log"
$watcherErr = Join-Path $watcherLogDir "staging_watcher_stderr.log"

Write-Host "Yeni şablon izleyici başlatılıyor..." -ForegroundColor Cyan
$watcherProcess = Start-Process -FilePath "python" -ArgumentList @($WatcherPath) -WorkingDirectory $RepoRoot -RedirectStandardOutput $watcherOut -RedirectStandardError $watcherErr -PassThru
Start-Sleep -Milliseconds 700

if ($watcherProcess.HasExited) {
    Write-Host "HATA: Şablon izleyici başlatılamadı." -ForegroundColor Red
    Write-Host "Log: $watcherErr"
    if (Test-Path -LiteralPath $watcherErr) {
        Get-Content -LiteralPath $watcherErr -Tail 20 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host $_ }
    }
    Read-Host "Kapatmak için Enter"
    exit 7
}

Write-Host "Şablon izleyici aktif. PID: $($watcherProcess.Id)" -ForegroundColor Green
Write-Host "İzlenen klasör: $(Join-Path $runtime 'YENI-BOS MOCKUP SABLON HAVUZU')" -ForegroundColor Green

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
