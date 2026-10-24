# V4.6.1 - Windows 10/11 PowerShell 5.1+ / safe Real-ESRGAN installer
# Installs official NCNN binary and models alongside existing kalite_motoru.py.
# Operator-run only. Never writes user templates, SQLite databases or production output.
param([switch]$SkipGpuSmoke)
$ErrorActionPreference='Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$repo=Split-Path -Parent $MyInvocation.MyCommand.Path
$target=Join-Path $repo 'AI_Kalite_Artirici'
$exe=Join-Path $target 'realesrgan-ncnn-vulkan.exe'
$source='https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip'
# Recorded from official asset downloaded during the user's 24 Oct 2026 run.
$expectedSha='ABC02804E17982A3BE33675E4D471E91EA374E65B70167ABC09E31ACB412802D'
$work=Join-Path ([System.IO.Path]::GetTempPath()) ('GM_ESRGAN_'+[Guid]::NewGuid().ToString('N'))
$archive=Join-Path $work 'official_windows.zip'
$unpacked=Join-Path $work 'unpacked'
$receipt=Join-Path $repo 'REAL_ESRGAN_KURULUM_SONUC.txt'
function Check-Engine([string]$root) {
  $engine=Join-Path $root 'realesrgan-ncnn-vulkan.exe'
  $models=Join-Path $root 'models'
  if (-not (Test-Path -LiteralPath $engine -PathType Leaf)) { throw 'realesrgan-ncnn-vulkan.exe bulunamadi.' }
  foreach ($file in @('realesrgan-x4plus.bin','realesrgan-x4plus.param')) {
    if (-not (Test-Path -LiteralPath (Join-Path $models $file) -PathType Leaf)) { throw "Eksik model: $file" }
  }
  if ((Get-Item -LiteralPath $engine).Length -le 0) { throw 'Bos EXE dosyasi.' }
}
$installed=$false
try {
  if (Test-Path -LiteralPath $exe -PathType Leaf) {
    try {
      Check-Engine $target
      Write-Host "[OK] Real-ESRGAN zaten kurulu: $exe" -ForegroundColor Green
      $installed=$true
    } catch {
      Write-Host '[BILGI] Eksik kurulum bulundu. Resmi dosyalarla, uzerine yazmadan tamamlama denenecek.' -ForegroundColor Yellow
    }
  }
  if (-not $installed) {
    New-Item -ItemType Directory -Path $work,$unpacked -Force | Out-Null
    Write-Host '[1/4] Resmi Real-ESRGAN Windows paketi indiriliyor...' -ForegroundColor Cyan
    Write-Host "Kaynak: $source"
    Invoke-WebRequest -Uri $source -OutFile $archive -UseBasicParsing -MaximumRedirection 8
    $size=(Get-Item -LiteralPath $archive).Length
    if ($size -lt 1MB -or $size -gt 500MB) { throw 'Indirme boyutu beklenenden farkli; kurulum iptal.' }
    $hash=(Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
    Write-Host "[2/4] Indirilen resmi arsiv SHA-256: $hash" -ForegroundColor Cyan
    if ($hash -ne $expectedSha) { throw "Resmi arsiv SHA-256 beklenen degerle uyusmuyor. Beklenen: $expectedSha ; indirilen: $hash . Guvenlik icin kurulum iptal." }
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip=[System.IO.Compression.ZipFile]::OpenRead($archive)
    try {
      foreach ($entry in $zip.Entries) {
        $name=$entry.FullName.Replace('\','/')
        if ($name.StartsWith('/') -or $name -match '(^|/)\.\.(/|$)' -or $name -match '^[A-Za-z]:' -or $name.Contains(':')) {
          throw "Guvenli olmayan arsiv girdisi: $name"
        }
      }
    } finally { $zip.Dispose() }
    Expand-Archive -LiteralPath $archive -DestinationPath $unpacked -Force
    $found=@(Get-ChildItem -LiteralPath $unpacked -Recurse -File -Filter 'realesrgan-ncnn-vulkan.exe')
    if ($found.Count -ne 1) { throw "Exe sayisi $($found.Count); beklenen 1. Kurulum durduruldu." }
    $sourceDir=$found[0].Directory.FullName
    Check-Engine $sourceDir
    # The application already ships AI_Kalite_Artirici/kalite_motoru.py and
    # README_windows.md. They MUST remain untouched. Stage only required
    # native executable, any DLL dependencies, and its model files.
    $installFiles=@($found[0])
    $installFiles+=@(Get-ChildItem -LiteralPath $sourceDir -File -Filter '*.dll')
    $modelDir=Join-Path $sourceDir 'models'
    $installFiles+=@(Get-ChildItem -LiteralPath $modelDir -Recurse -File)
    if (Test-Path -LiteralPath $target -PathType Leaf) { throw "Kurulum hedefi klasor degil: $target" }
    # First inspect every collision, before writing even one file.
    $installPlan=@()
    foreach ($item in $installFiles) {
      $relative=$item.FullName.Substring($sourceDir.Length+1)
      $destination=Join-Path $target $relative
      if (Test-Path -LiteralPath $destination) {
        if (-not (Test-Path -LiteralPath $destination -PathType Leaf)) {throw "Dosya yolunda klasor cakismasi: $destination"}
        $oldHash=(Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
        $newHash=(Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash
        if ($oldHash -ne $newHash) {throw "Varolan Real-ESRGAN dosyasi farkli; uzerine yazilmadi: $destination"}
      } else {
        $installPlan+=@([pscustomobject]@{Source=$item.FullName;Destination=$destination})
      }
    }
    Write-Host '[3/4] Orijinal Python araci korunuyor; sadece eksik EXE, DLL ve modeller kuruluyor...' -ForegroundColor Cyan
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    foreach ($item in $installPlan) {
      $parent=Split-Path -Parent $item.Destination
      New-Item -ItemType Directory -Path $parent -Force | Out-Null
      # Fail closed rather than replacing anything if another process created it.
      if (Test-Path -LiteralPath $item.Destination) {throw "Kurulum sirasinda dosya cakismasi: $($item.Destination)"}
      Copy-Item -LiteralPath $item.Source -Destination $item.Destination -ErrorAction Stop
    }
    Check-Engine $target
    Write-Host "[OK] EXE ve modeller hazir: $target" -ForegroundColor Green
  }
  $fast=(Test-Path -LiteralPath (Join-Path $target 'models/realesr-general-x4v3.bin')) -and
        (Test-Path -LiteralPath (Join-Path $target 'models/realesr-general-x4v3.param'))
  Write-Host "[4/4] Photo modeli: OK; Fast modeli: $(if($fast){'OK'}else{'YOK - hizli profili secmeyin'})" -ForegroundColor Cyan
  $status='DOSYALAR_OK'
  if (-not $SkipGpuSmoke) {
    Write-Host '[GPU] 64x64 piksellik test goruntusu ile Vulkan deneniyor...' -ForegroundColor Cyan
    $smokeDir=Join-Path ([System.IO.Path]::GetTempPath()) ('GM_ESRGAN_SMOKE_'+[Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $smokeDir | Out-Null
    try {
      Add-Type -AssemblyName System.Drawing
      $input=Join-Path $smokeDir 'input.png'
      $output=Join-Path $smokeDir 'output.png'
      $bmp=New-Object System.Drawing.Bitmap(64,64)
      try {
        $g=[System.Drawing.Graphics]::FromImage($bmp)
        try {$g.Clear([System.Drawing.Color]::FromArgb(90,140,170))} finally {$g.Dispose()}
        $bmp.Save($input,[System.Drawing.Imaging.ImageFormat]::Png)
      } finally {$bmp.Dispose()}
      $proc=Start-Process -FilePath $exe -ArgumentList @('-i',$input,'-o',$output,'-n','realesrgan-x4plus','-s','4','-t','64','-m',(Join-Path $target 'models')) -Wait -PassThru -NoNewWindow
      if ($proc.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $output -PathType Leaf)) {throw "Real-ESRGAN GPU smoke basarisiz (kod $($proc.ExitCode))."}
      Write-Host '[PASS] Vulkan GPU gercek gorsel testi BASARILI!' -ForegroundColor Green
      $status='GPU_SMOKE_PASS'
    } finally {Remove-Item -LiteralPath $smokeDir -Recurse -Force -ErrorAction SilentlyContinue}
  }
  @("Real-ESRGAN Windows kurulum sonucu: $status", "Exe: $exe", "Foto model: realesrgan-x4plus OK", "Hizli model mevcut: $fast", "Arsiv SHA-256: $expectedSha", "Kaynak: $source", "Zaman: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')") |
    Set-Content -LiteralPath $receipt -Encoding UTF8
  Write-Host "[SONUC] $status | $receipt" -ForegroundColor Green
  exit 0
} catch {
  Write-Host "[HATA] Real-ESRGAN kurulum/testi tamamlanamadi: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host 'Normal (4K kapali) uretim devam edebilir. Onayli 4 kose ve veritabanlari degismedi.'
  @('Real-ESRGAN KURULUM/KONTROL BASARISIZ', $_.Exception.ToString()) | Set-Content -LiteralPath $receipt -Encoding UTF8
  exit 1
} finally {
  if (Test-Path -LiteralPath $work) {Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue}
}
