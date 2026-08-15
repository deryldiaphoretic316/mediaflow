# Build a self-contained MediaFlow portable folder for Windows (Variant A).
#
# Output: dist\MediaFlow-portable\
#   MediaFlow.exe
#   README.txt
#   app.py, static\, runtime\ (embeddable Python + deps)
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\pack-portable.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\pack-portable.ps1 -SkipBuild

param(
    [switch]$SkipBuild,
    [string]$PythonVersion = "3.12.10",
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) {
    $OutDir = Join-Path $Root "dist\MediaFlow-portable"
}

$Parts = $PythonVersion.Split('.')
$PyShort = "$($Parts[0])$($Parts[1])"  # 3.12.10 -> 312
$EmbedZipName = "python-$PythonVersion-embed-amd64.zip"
$EmbedUrl = "https://www.python.org/ftp/python/$PythonVersion/$EmbedZipName"
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"

Write-Host "==> Repo root: $Root"
Write-Host "==> Output:    $OutDir"

if (-not $SkipBuild) {
    Write-Host "==> Building MediaFlow.exe (tauri build --no-bundle)..."
    Push-Location $Root
    try {
        if (-not (Test-Path (Join-Path $Root "node_modules"))) {
            npm install
        }
        npm run tauri -- build --no-bundle
    } finally {
        Pop-Location
    }
}

$ExeCandidates = @(
    (Join-Path $Root "src-tauri\target\release\MediaFlow.exe"),
    (Join-Path $Root "src-tauri\target\release\mediaflow-tauri.exe")
)
$ExePath = $ExeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $ExePath) {
    throw "Release executable not found. Run without -SkipBuild, or build first."
}
Write-Host "==> Using exe: $ExePath"

# Fresh output folder
if (Test-Path $OutDir) {
    Remove-Item -Recurse -Force $OutDir
}
New-Item -ItemType Directory -Path $OutDir | Out-Null
$RuntimeDir = Join-Path $OutDir "runtime"
$CacheDir = Join-Path $Root "dist\.cache"
New-Item -ItemType Directory -Path $CacheDir -Force | Out-Null

# --- Embeddable Python ---
$ZipPath = Join-Path $CacheDir $EmbedZipName
if (-not (Test-Path $ZipPath)) {
    Write-Host "==> Downloading $EmbedUrl"
    Invoke-WebRequest -Uri $EmbedUrl -OutFile $ZipPath
} else {
    Write-Host "==> Using cached $EmbedZipName"
}

Write-Host "==> Extracting embeddable Python -> runtime\"
Expand-Archive -Path $ZipPath -DestinationPath $RuntimeDir -Force

# Enable site-packages (required for pip-installed modules)
$PthFile = Get-ChildItem -Path $RuntimeDir -Filter "python*._pth" | Select-Object -First 1
if (-not $PthFile) {
    throw "python*._pth not found in embeddable runtime"
}
$PthLines = @(
    "python$PyShort.zip"
    "."
    "Lib\\site-packages"
    "import site"
)
Set-Content -Path $PthFile.FullName -Value ($PthLines -join "`n") -NoNewline -Encoding ASCII
Add-Content -Path $PthFile.FullName -Value "`n" -Encoding ASCII

$PythonExe = Join-Path $RuntimeDir "python.exe"
$GetPip = Join-Path $CacheDir "get-pip.py"
if (-not (Test-Path $GetPip)) {
    Write-Host "==> Downloading get-pip.py"
    Invoke-WebRequest -Uri $GetPipUrl -OutFile $GetPip
}

Write-Host "==> Installing pip into runtime"
& $PythonExe $GetPip --no-warn-script-location
if ($LASTEXITCODE -ne 0) { throw "get-pip.py failed" }

Write-Host "==> Installing requirements.txt into runtime"
$Req = Join-Path $Root "requirements.txt"
& $PythonExe -m pip install --no-warn-script-location -r $Req
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

# Smoke-check uvicorn import
& $PythonExe -c "import uvicorn, fastapi, PIL; print('runtime ok')"
if ($LASTEXITCODE -ne 0) { throw "runtime import check failed" }

# --- App files ---
Write-Host "==> Copying app files"
Copy-Item $ExePath (Join-Path $OutDir "MediaFlow.exe")
Copy-Item (Join-Path $Root "app.py") (Join-Path $OutDir "app.py")
Copy-Item (Join-Path $Root "scripts\portable-README.txt") (Join-Path $OutDir "README.txt")
Copy-Item (Join-Path $Root "static") (Join-Path $OutDir "static") -Recurse

# Optional: drop a clean settings example name (not required at runtime)
# Do NOT copy developer settings.json

Write-Host ""
Write-Host "Portable pack ready:"
Write-Host "  $OutDir"
Write-Host "  Run MediaFlow.exe from that folder (keep runtime\ + app.py + static\ together)."

# --- Zip for distribution / GitHub Releases ---
$Version = "0.1.0"
$PkgJson = Join-Path $Root "package.json"
if (Test-Path $PkgJson) {
    $m = Select-String -Path $PkgJson -Pattern '"version"\s*:\s*"([^"]+)"' | Select-Object -First 1
    if ($m) { $Version = $m.Matches[0].Groups[1].Value }
}
$ReleasesDir = Join-Path $Root "releases"
New-Item -ItemType Directory -Path $ReleasesDir -Force | Out-Null
$ZipName = "MediaFlow-portable-$Version-win64.zip"
$ZipPath = Join-Path $ReleasesDir $ZipName
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Write-Host "==> Creating $ZipPath"
Compress-Archive -Path (Join-Path $OutDir "*") -DestinationPath $ZipPath -CompressionLevel Optimal
Copy-Item $ZipPath (Join-Path $Root "dist\$ZipName") -Force
Write-Host "  Zip: $ZipPath"
