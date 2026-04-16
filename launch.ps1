#Requires -Version 7
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$PythonExe = "python3.12"

# Try to find python3.12 on PATH, fallback to python
if (-not (Get-Command $PythonExe -ErrorAction SilentlyContinue)) {
    $PythonExe = "python"
    $verOutput = & $PythonExe --version 2>&1
    if ($verOutput -notmatch "Python 3\.12") {
        Write-Error "Python 3.12 not found. Please install Python 3.12 and ensure it is on PATH."
        exit 1
    }
}

$VenvDir = ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

# Recreate venv if missing or broken
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment..."
    if (Test-Path $VenvDir) { Remove-Item -Recurse -Force $VenvDir }
    & $PythonExe -m venv $VenvDir
}

# Activate
$ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
& $ActivateScript

# Upgrade pip
python -m pip install --upgrade pip -q

# Install requirements
python -m pip install -r requirements.txt -q

# Launch
python -m app.main
