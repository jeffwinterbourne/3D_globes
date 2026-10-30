<#
.SYNOPSIS
    Launches the Globe3D Studio Web Application (FastAPI Backend + React/Three.js Frontend).
.DESCRIPTION
    1. Activates the pygmt Conda environment.
    2. Starts the FastAPI backend (WebApp.backend.main:app) on http://127.0.0.1:8000.
    3. Installs frontend Node dependencies if node_modules is missing.
    4. Starts the Vite frontend server on http://localhost:5173 and opens the browser.
#>

param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$WebAppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $WebAppDir
$FrontendDir = Join-Path $WebAppDir "frontend"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Globe3D Studio - 3D Printable Geophysical and Paleo CAD" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Repository Root : $RepoRoot"
Write-Host "WebApp Root     : $WebAppDir"

# 1. Start FastAPI Backend in conda activate pygmt
Write-Host ""
Write-Host "[1/3] Starting Python FastAPI Backend on http://127.0.0.1:$BackendPort (conda env: pygmt)..." -ForegroundColor Green
$CondaInit = "if (Test-Path 'C:\ProgramData\anaconda3\shell\condabin\conda-hook.ps1') { . 'C:\ProgramData\anaconda3\shell\condabin\conda-hook.ps1' }; conda activate pygmt"
$BackendReq = Join-Path $WebAppDir "backend\requirements.txt"
$BackendCmd = "$CondaInit; Set-Location '$RepoRoot'; python -c 'import fastapi, uvicorn' 2>`$null; if (`$LASTEXITCODE -ne 0) { pip install --user -r '$BackendReq' }; python -m uvicorn WebApp.backend.main:app --host 127.0.0.1 --port $BackendPort --reload"
$BackendProc = Start-Process powershell -ArgumentList "-NoExit", "-Command", $BackendCmd -PassThru

# 2. Check Node/npm PATH and Frontend Dependencies
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    if (Test-Path "F:\pinokio\bin\miniforge\node.exe") {
        $env:PATH = "F:\pinokio\bin\miniforge;$env:PATH"
    }
}
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host ""
    Write-Host "[2/3] Installing Frontend npm dependencies in $FrontendDir..." -ForegroundColor Yellow
    Push-Location $FrontendDir
    npm install
    Pop-Location
} else {
    Write-Host ""
    Write-Host "[2/3] Frontend node_modules already installed." -ForegroundColor Green
}

# 3. Start Vite Dev Server and Open Browser
Write-Host ""
Write-Host "[3/3] Starting Vite Frontend Server on http://localhost:$FrontendPort..." -ForegroundColor Green
$FrontendCmd = "if (-not (Get-Command npm -ErrorAction SilentlyContinue) -and (Test-Path 'F:\pinokio\bin\miniforge\node.exe')) { `$env:PATH = 'F:\pinokio\bin\miniforge;' + `$env:PATH }; Set-Location '$FrontendDir'; npm run dev -- --port $FrontendPort"
$FrontendProc = Start-Process powershell -ArgumentList "-NoExit", "-Command", $FrontendCmd -PassThru

Start-Sleep -Seconds 3
if (-not $NoBrowser) {
    $Url = "http://localhost:$FrontendPort"
    Write-Host ""
    Write-Host "Opening $Url in default browser..." -ForegroundColor Cyan
    Start-Process $Url
}

Write-Host ""
Write-Host "Globe3D Studio is running!" -ForegroundColor Green
Write-Host "  - Frontend UI : http://localhost:$FrontendPort"
Write-Host "  - Backend API : http://127.0.0.1:$BackendPort/docs"
Write-Host "Close the spawned PowerShell windows to stop the servers."
