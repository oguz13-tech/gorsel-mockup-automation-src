$Shell = New-Object -ComObject Shell.Application
$RecycleBin = $Shell.NameSpace(10)
$Items = $RecycleBin.Items()
$Found = $false
foreach ($item in $Items) {
    if ($item.Name -match "Ocak|YEDEK|M00|png|jpg") {
        Write-Host "Name: $($item.Name) | OriginalPath: $($item.Path)"
        $Found = $true
    }
}
if (-not $Found) {
    Write-Host "No matching files found in Recycle Bin."
}
