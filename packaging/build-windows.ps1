# Builds dist\nexplorer-vX.Y.Z-windows-x64.zip on a Windows x64 machine.
# The zip holds one root folder nexplorer-vX.Y.Z\ with nexplorer.exe and its libraries.
# The version comes from pyproject.toml. Needs Python 3.10+ on the PATH.
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$match = Select-String -Path pyproject.toml -Pattern '^version\s*=\s*"(.*)"' | Select-Object -First 1
if (-not $match) { throw "version not found in pyproject.toml" }
$version = $match.Matches[0].Groups[1].Value
$folder = "nexplorer-v$version"
$zip = Join-Path $root "dist\$folder-windows-x64.zip"

$build = Join-Path $root "build"
$venv = Join-Path $build "venv"
$stage = Join-Path $build "stage"
foreach ($path in @((Join-Path $build "lib"), (Join-Path $build "pyinstaller"), $stage, $zip)) {
    if (Test-Path $path) { Remove-Item -Recurse -Force $path }
}
New-Item -ItemType Directory -Force $build, (Join-Path $root "dist") | Out-Null

# Build dependencies
if (-not (Test-Path $venv)) { python -m venv $venv; if ($LASTEXITCODE) { throw "venv failed" } }
$python = Join-Path $venv "Scripts\python.exe"
& $python -m pip install --quiet --upgrade pip
& $python -m pip install --quiet $root pyinstaller
if ($LASTEXITCODE) { throw "pip install failed" }

# Bundle (directory mode)
& $python -m PyInstaller --noconfirm --clean `
    --distpath (Join-Path $build "pyinstaller\dist") --workpath (Join-Path $build "pyinstaller\work") `
    packaging\nexplorer.spec
if ($LASTEXITCODE) { throw "PyInstaller failed" }

# Single root folder, then zip
New-Item -ItemType Directory -Force $stage | Out-Null
Copy-Item -Recurse (Join-Path $build "pyinstaller\dist\nexplorer") (Join-Path $stage $folder)
foreach ($file in "LICENSE", "THIRD_PARTY_NOTICES.md", "README.md") {
    Copy-Item $file (Join-Path $stage $folder)
}
Compress-Archive -Path (Join-Path $stage $folder) -DestinationPath $zip

$size = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host "zip: $size MB  dist\$folder-windows-x64.zip"
