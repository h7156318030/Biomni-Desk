# Biomni-Lite one-click installer for Windows.
# Usage: double-click install.bat, or run:  powershell -ExecutionPolicy Bypass -File install.ps1 [-Core]
#   -Core   install only the core packages (no scanpy, rdkit and other large analysis packages)

param([switch]$Core)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Write-Step($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host ""; Write-Host "ERROR: $text" -ForegroundColor Red; Read-Host "Press Enter to close"; exit 1 }

Write-Step "Checking Python (3.12)"
$pyExe = $null
$pyArgs = @()
$candidates = @(
    @{ Exe = "py"; Args = @("-3.12") },
    @{ Exe = "python"; Args = @() }
)
foreach ($c in $candidates) {
    try {
        $ver = & $c.Exe @($c.Args) -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $ver -eq "3.12") {
            $pyExe = $c.Exe
            $pyArgs = $c.Args
            break
        }
    } catch { }
}
if (-not $pyExe) { Fail "Python 3.12 was not found. Install Python 3.12 from https://www.python.org/downloads/ (tick 'Add python.exe to PATH') and run this again." }
Write-Host "Using Python $ver ($pyExe $($pyArgs -join ' '))"

Write-Step "Checking Node.js (20 or newer)"
$nodever = $null
try { $nodever = (& node -v) } catch { $nodever = $null }
if (-not $nodever) { Fail "Node.js was not found. Install the LTS version from https://nodejs.org/ and run this again." }
$major = [int]($nodever.TrimStart("v").Split(".")[0])
if ($major -lt 20) { Fail "Node.js $nodever is too old. Install version 20 or newer." }
Write-Host "Node.js $nodever"

Write-Step "Creating the Python environment (.venv)"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $pyExe @pyArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { Fail "Could not create the virtual environment." }
}
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
& $venvPy -m pip install --upgrade pip | Out-Null

Write-Step "Installing Python packages (this can take several minutes)"
$req = "requirements.txt"
if ($Core) {
    # the core block is everything before the analysis-packages comment
    $text = Get-Content $req -Raw
    $core = $text.Split("# Analysis packages")[0]
    Set-Content -Path ".requirements-core.txt" -Value $core -Encoding UTF8
    $req = ".requirements-core.txt"
}
& $venvPy -m pip install -r $req
if ($LASTEXITCODE -ne 0) { Fail "Installing the Python packages failed. Read the messages above, fix the cause and run this again." }

Write-Step "Preparing the settings file and data folder"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. No keys are set: add your model keys in the app's Settings page."
}
New-Item -ItemType Directory -Force -Path "ui_data" | Out-Null

Write-Step "Building the web page (first time only, about a minute)"
Push-Location (Join-Path $Root "web")
& npm install
if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "npm install failed." }
& npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "The web page build failed." }
Pop-Location

Write-Host ""
Write-Host "Installed. Start Biomni-Lite with start.bat, then open http://localhost:3001" -ForegroundColor Green
Read-Host "Press Enter to close"
