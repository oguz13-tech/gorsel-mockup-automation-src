param(
    [string]$Root = 'C:\GorselUretimMerkezi',
    [switch]$NoExplorer
)
# Görsel Üretim Merkezi: iki aktif ağaçtan yalnızca inceleme amaçlı metin kaynaklarını tek ZIP'te birleştirir.
# Kaynak kod, veri tabanı, maskeler, görüntüler ve çalışma kayıtları DEĞİŞTİRİLMEZ.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$base = [System.IO.Path]::GetFullPath($Root)
$active = Join-Path $base 'CODEX_ACTIVE'
$outputDir = Join-Path $base 'INCELEME_PAKETLERI'
$fileStamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$outputName = 'CODEX_CIFT_KAYNAK_INCELEME_' + $fileStamp + '.zip'
$output = Join-Path $outputDir $outputName
$staging = Join-Path $outputDir ('.' + $outputName + '.partial')
foreach ($path in @($base, $active)) {
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        throw "Gerekli klasör bulunamadı: $path"
    }
}

if (-not (Test-Path -LiteralPath $outputDir -PathType Container)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

# Hassas veri/çıktı/önbellek dizinleri. Bu liste her sıralı ağaç için geçerlidir.
$skipDirs = @(
    'inceleme_paketleri','.git','.venv','venv','env','node_modules','__pycache__','.pytest_cache',
    '.mypy_cache','.ruff_cache','.vscode','.idea','dist','build','cache','caches',
    'logs','log','tmp','temp','output','outputs','production','generated',
    'uploads','downloads','working','working_art_proxies','originals',
    'masks','maskeler','profiles','weights','models','datasets','data',
    'assets','review_artifacts','kalite_kontrol_gorselleri',
    '1_gelen_kaggle_baskilari','2_sablon_havuzu','2_sablon_havuzu_orijinal_yedek',
    'ham baski tasarimlari','ham_baski_tasarimlari','gorseller','görseller',
    'fotograflar','fotoğraflar','4k','esrgan'
)
$allowedExts = @('.py','.pyi','.js','.jsx','.ts','.tsx','.css','.html','.htm',
                 '.bat','.cmd','.ps1','.sh','.md','.rst','.txt','.toml','.ini',
                 '.cfg','.yaml','.yml','.sql','.xml','.svg','.gitignore')
$exactNames = @('.gitignore','.gitattributes','.editorconfig','Dockerfile',
                'Makefile','requirements.txt','requirements-dev.txt',
                'requirements.lock','pytest.ini','pyproject.toml','setup.py',
                'setup.cfg','tox.ini','package.json')
$skipFile = '(?i)(^\.env($|\.)|^ayarlar\.|^settings\.json$|^config\.json$|secret|credential|password|private.?key|token|api.?key|anahtar|store.?profiles|ma[gğ]aza.*\.json$|\.log$|\.db($|[-.])|\.sqlite|\.pkl$|\.pickle$|\.bak$|\.old$|\.zip$|\.exe$|\.dll$|\.pth$|\.pt$|\.onnx$|\.npy$|\.npz$|\.csv$|\.xlsx?$)'
$maxFile = 4MB
$maxTotal = 120MB
$entries = New-Object System.Collections.Generic.List[object]
$totalBytes = [long]0
$ignoredLarge = 0

foreach ($scan in @(@{ Path=$base; Prefix='KOK' }, @{ Path=$active; Prefix='CODEX_ACTIVE' })) {
    $stack = New-Object 'System.Collections.Stack'
    $scanPath = [string]$scan['Path']
    $scanPrefix = [string]$scan['Prefix']
    $stack.Push((Get-Item -LiteralPath $scanPath))
    while ($stack.Count -gt 0) {
        $dir = $stack.Pop()
        foreach ($sub in @(Get-ChildItem -LiteralPath $dir.FullName -Directory -Force -ErrorAction SilentlyContinue)) {
            if ($scanPrefix -eq 'KOK' -and $sub.FullName -ieq $active) { continue }
            if ($skipDirs -contains $sub.Name.ToLowerInvariant()) { continue }
            if (($sub.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { continue }
            $stack.Push($sub)
        }
        foreach ($f in @(Get-ChildItem -LiteralPath $dir.FullName -File -Force -ErrorAction SilentlyContinue)) {
            if (($f.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { continue }
            if ($f.Name -match $skipFile) { continue }
            if (-not (($allowedExts -contains $f.Extension.ToLowerInvariant()) -or ($exactNames -contains $f.Name))) { continue }
            if ($f.Length -gt $maxFile) { $ignoredLarge++; continue }
            $rel = $f.FullName.Substring($scanPath.Length).TrimStart('\','/') -replace '\\','/'
            $entries.Add([pscustomobject]@{ Source=$f.FullName; Zip=($scanPrefix + '/' + $rel); Size=$f.Length })
            $totalBytes += $f.Length
        }
    }
}
if ($entries.Count -eq 0) { throw 'İncelenecek kaynak dosyası bulunamadı.' }
$rootCount = @($entries | Where-Object { $_.Zip -like 'KOK/*' }).Count
$activeCount = @($entries | Where-Object { $_.Zip -like 'CODEX_ACTIVE/*' }).Count
if ($rootCount -eq 0 -or $activeCount -eq 0) {
    throw "Her iki kaynak agacinda da kaynak dosyasi bulunmalidir. KOK=$rootCount, CODEX_ACTIVE=$activeCount."
}
if ($totalBytes -gt $maxTotal) { throw "Kaynak dosyaları 120 MB sınırını aşıyor: $([math]::Round($totalBytes / 1MB,1)) MB. ZIP oluşturulmadı." }
if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Force }
$fs = $null
try {
    $fs = [System.IO.File]::Open($staging, [System.IO.FileMode]::CreateNew)
    $zip = New-Object System.IO.Compression.ZipArchive($fs,[System.IO.Compression.ZipArchiveMode]::Create,$false)
    try {
        foreach ($e in ($entries | Sort-Object Zip)) {
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $zip, $e.Source, $e.Zip, [System.IO.Compression.CompressionLevel]::Optimal
            ) | Out-Null
        }
        $note = $zip.CreateEntry('INCELEME_NOTU.txt')
        $writer = New-Object System.IO.StreamWriter($note.Open(), [System.Text.Encoding]::UTF8)
        try {
            $writer.WriteLine('Gorsel Uretim Merkezi - IKI AGACTAN kaynak kod inceleme paketi')
            $writer.WriteLine('Olusturulma: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'))
            $writer.WriteLine('KOK/ = C:\GorselUretimMerkezi icindeki CODEX_ACTIVE disi kaynaklar')
            $writer.WriteLine('CODEX_ACTIVE/ = C:\GorselUretimMerkezi\CODEX_ACTIVE kaynaklari')
            $writer.WriteLine('Iki agac ayri tutulur; hangisinin calisma zamaninda hangi gorevde oldugu koddan dogrulanmalidir.')
            $writer.WriteLine('KOK kaynak dosya sayisi: ' + $rootCount)
            $writer.WriteLine('CODEX_ACTIVE kaynak dosya sayisi: ' + $activeCount)
            $writer.WriteLine('Veritabani, maskeler, resimler, modeller, ayarlar ve kullanici ciktilari alinmamistir.')
            $writer.WriteLine('Dahil dosya: ' + $entries.Count + '; kaynak toplam MB: ' + [math]::Round($totalBytes/1MB,2))
            $writer.WriteLine('Buyuk oldugu icin atlanan metin dosyasi: ' + $ignoredLarge)
            $writer.WriteLine('UYARI: Metin kaynaklarinda elle yazilmis gizli bilgiler bulunabilir; yuklemeden once ZIP icerigini gozden gecirin.')
            $writer.WriteLine('Bu paket kod incelemesi icindir; programin tam yedegi veya geri yukleme paketi DEGILDIR.')
        } finally { $writer.Dispose() }
        $manifestEntry = $zip.CreateEntry('PAKET_DOSYA_LISTESI.tsv')
        $manifestWriter = New-Object System.IO.StreamWriter($manifestEntry.Open(), [System.Text.Encoding]::UTF8)
        try {
            $manifestWriter.WriteLine("ZIP_YOLU`tBOYUT_BAYT")
            foreach ($entry in ($entries | Sort-Object Zip)) {
                $manifestWriter.WriteLine($entry.Zip + "`t" + $entry.Size)
            }
        } finally { $manifestWriter.Dispose() }
    } finally { $zip.Dispose(); $fs.Dispose(); $fs = $null }
    # ZIP merkezi dizinini yeniden acarak dosyanin okunabildigini dogrula.
    $checkArchive = [System.IO.Compression.ZipFile]::OpenRead($staging)
    try {
        if ($checkArchive.Entries.Count -lt ($entries.Count + 2)) {
            throw 'ZIP dogrulama basarisiz: eksik dosya girdisi.'
        }
    } finally { $checkArchive.Dispose() }
    Move-Item -LiteralPath $staging -Destination $output
} catch {
    if ($fs) { $fs.Dispose() }
    if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Force -ErrorAction SilentlyContinue }
    throw
}
Write-Host ''
Write-Host 'IKI AKTIF KLASOR ICIN INCELEME PAKETI HAZIR.' -ForegroundColor Green
Write-Host $output
Write-Host ("Dosya sayisi: {0}; ZIP: {1:N2} MB" -f $entries.Count, ((Get-Item -LiteralPath $output).Length / 1MB))
Write-Host 'Bu dosyayi ChatGPT sohbetine yukleyebilirsiniz. Kaynak klasorler degistirilmedi.'
Write-Host "KOK=$rootCount, CODEX_ACTIVE=$activeCount"
$zipHash = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash
$hashPath = $output + '.sha256.txt'
[System.IO.File]::WriteAllText($hashPath, ($zipHash + '  ' + $outputName + [Environment]::NewLine), [System.Text.Encoding]::UTF8)
Write-Host ('SHA256: ' + $zipHash)
Write-Output ('ZIP_OUTPUT=' + $output)
if (-not $NoExplorer) {
    try {
        # Windows Explorer'da olusan ZIP'i secili goster.
        Start-Process -FilePath 'explorer.exe' -ArgumentList ('/select,"{0}"' -f $output) -ErrorAction Stop
    } catch {
        Write-Warning ('ZIP olustu ancak Explorer otomatik acilamadi: ' + $_.Exception.Message)
        try { Start-Process -FilePath 'explorer.exe' -ArgumentList ('"{0}"' -f $outputDir) -ErrorAction Stop } catch { }
    }
}
