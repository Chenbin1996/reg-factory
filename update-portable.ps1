param(
    [Parameter(Mandatory = $true)]
    [string]$InstallDir,
    [int]$ProcessId = 0
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)
$parentDir = Split-Path -Parent $InstallDir
if ([string]::IsNullOrWhiteSpace($parentDir) -or $InstallDir -eq $parentDir) {
    throw "Refusing to update an unsafe installation path: $InstallDir"
}
if (-not (Test-Path -LiteralPath (Join-Path $InstallDir "reg-factory.exe"))) {
    throw "Portable executable not found: $InstallDir"
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("reg-factory-portable-update-" + [guid]::NewGuid())
$archivePath = Join-Path $tempRoot "latest.zip"
$extractRoot = Join-Path $tempRoot "extract"
$backupDir = Join-Path $parentDir (".reg-factory-backup-" + [guid]::NewGuid())
$movedOld = $false
$movedNew = $false

New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null
try {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/tiantianGPU/reg-factory/releases/latest" -Headers @{ Accept = "application/vnd.github+json" }
    $asset = @($release.assets) | Where-Object {
        $_.name -match '^reg-factory-windows-x64-.*\.zip$'
    } | Select-Object -First 1
    if ($null -eq $asset -or [string]::IsNullOrWhiteSpace($asset.browser_download_url)) {
        throw "Latest GitHub Release has no portable Windows package"
    }

    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $archivePath
    Expand-Archive -LiteralPath $archivePath -DestinationPath $extractRoot -Force
    $source = Get-ChildItem -LiteralPath $extractRoot -Directory | Where-Object {
        Test-Path -LiteralPath (Join-Path $_.FullName "reg-factory.exe")
    } | Select-Object -First 1
    if ($null -eq $source) {
        throw "Downloaded package layout is invalid"
    }

    if ($ProcessId -gt 0) {
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
        for ($i = 0; $i -lt 30; $i++) {
            if ($null -eq (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) { break }
            Start-Sleep -Milliseconds 500
        }
        if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
            throw "The current reg-factory process did not stop"
        }
    }

    Move-Item -LiteralPath $InstallDir -Destination $backupDir
    $movedOld = $true
    Move-Item -LiteralPath $source.FullName -Destination $InstallDir
    $movedNew = $true
    Start-Process -FilePath (Join-Path $InstallDir "reg-factory.exe") -WorkingDirectory $InstallDir
    Remove-Item -LiteralPath $backupDir -Recurse -Force
    $movedOld = $false
    Write-Output "Portable update completed: $($release.tag_name)"
} catch {
    if ($movedNew -and (Test-Path -LiteralPath $InstallDir)) {
        Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($movedOld -and (Test-Path -LiteralPath $backupDir) -and -not (Test-Path -LiteralPath $InstallDir)) {
        Move-Item -LiteralPath $backupDir -Destination $InstallDir -Force
    }
    throw
} finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
