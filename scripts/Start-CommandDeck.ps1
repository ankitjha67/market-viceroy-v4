#Requires -Version 5.1
<#
.SYNOPSIS
  One-shot launcher for Market Viceroy v4 (paper): set up + start the API and UI
  and open the Command Deck. Built for this machine: Windows, uv + Node, no Docker.

.DESCRIPTION
  Run it and walk away. It:
    1. ensures the Python 3.12 virtual environment (rebuilds it only if broken),
    2. installs the UI dependencies if missing,
    3. frees ports 8000 / 3000 (so a re-run is clean),
    4. starts the API (mv-serve) and the UI (npm run dev), each in its own window,
    5. waits for both to be healthy,
    6. opens the deck in Edge InPrivate (extensions off -> no ad-blocker block).
  Paper only. No real-money order is ever placed. Re-run any time; it resets first.

.PARAMETER Agents
  Drive decisions with the LangGraph agent pipeline instead of the deterministic
  ensemble.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\Start-CommandDeck.ps1

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\Start-CommandDeck.ps1 -Agents
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = 'E:\Python\Market Viceroy v4',
    [int]$ApiPort = 8000,
    [int]$UiPort = 3000,
    # Empty -> reuse the token in .env, else generate a random one (never a
    # static default: this file is public, so a hardcoded token would hand
    # kill/reset/adopt/graduate rights to anyone who can reach the API).
    [string]$OperatorToken = '',
    [string]$Timeframe = '1m',
    [int]$IntervalSeconds = 60,
    [switch]$Agents
)

$ErrorActionPreference = 'Stop'

function Write-Step([string]$Message) { Write-Host "==> $Message" -ForegroundColor Cyan }

# Cryptographically random 32-byte hex token (same scheme as Start-MarketViceroy).
function New-OperatorToken {
    $bytes = New-Object 'System.Byte[]' 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return (([System.BitConverter]::ToString($bytes)) -replace '-', '').ToLower()
}

# Read a KEY=value from the git-ignored .env (returns $null when absent).
function Get-DotEnvValue([string]$Name) {
    $envFile = Join-Path $RepoRoot '.env'
    if (-not (Test-Path -LiteralPath $envFile)) { return $null }
    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -match ("^\s*" + [regex]::Escape($Name) + "\s*=\s*(.*)$")) {
            $value = $Matches[1].Trim().Trim('"').Trim("'")
            if ($value) { return $value }
        }
    }
    return $null
}

# Update-or-append KEY=value in the git-ignored .env.
function Set-DotEnvValue([string]$Name, [string]$Value) {
    $envFile = Join-Path $RepoRoot '.env'
    $line = "$Name=$Value"
    if (Test-Path -LiteralPath $envFile) {
        $content = Get-Content -LiteralPath $envFile
        $pattern = "^\s*" + [regex]::Escape($Name) + "\s*="
        if ($content -match $pattern) {
            $content = $content | ForEach-Object { if ($_ -match $pattern) { $line } else { $_ } }
        }
        else { $content = @($content) + $line }
        Set-Content -LiteralPath $envFile -Value $content -Encoding ascii
    }
    else { Set-Content -LiteralPath $envFile -Value @($line) -Encoding ascii }
}

# Kill whatever is listening on a port (clears stray mv-serve / next dev servers).
function Reset-Port([int]$Port) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        foreach ($procId in ($conns.OwningProcess | Select-Object -Unique)) {
            if ($procId) { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue }
        }
    }
    catch { }
}

# Launch a persistent PowerShell window running $Script (Base64 avoids quoting hell).
function Start-ServerWindow([string]$Script) {
    $enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Script))
    Start-Process powershell -ArgumentList '-NoExit', '-EncodedCommand', $enc | Out-Null
}

# --- 0. preflight ---------------------------------------------------------
if (-not (Test-Path -LiteralPath $RepoRoot)) { throw "Repo not found: $RepoRoot" }
Set-Location -LiteralPath $RepoRoot
# A self-contained launcher: clear any inherited Python env so uv resolves THIS
# project's venv, and avoid cross-filesystem hardlink warnings.
foreach ($v in 'UV_PYTHON', 'VIRTUAL_ENV', 'PYTHONHOME', 'PYTHONPATH', 'CONDA_PREFIX', 'CONDA_DEFAULT_ENV') {
    if (Test-Path "Env:$v") { Remove-Item "Env:$v" -ErrorAction SilentlyContinue }
}
$env:UV_LINK_MODE = 'copy'
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv is not installed. Install it from https://docs.astral.sh/uv/ and re-run.'
}

Write-Host ''
Write-Host 'Market Viceroy v4 - Command Deck launcher (paper)' -ForegroundColor White
Write-Host ''

# --- 1. Python venv + dependencies (fast path if the venv already runs) ---
Write-Step 'Ensuring Python 3.12'
uv python install 3.12

$venvPy = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$venvOk = $false
if (Test-Path -LiteralPath $venvPy) {
    try { & $venvPy --version *> $null; $venvOk = ($LASTEXITCODE -eq 0) } catch { $venvOk = $false }
}
if (-not $venvOk) {
    Write-Step 'Rebuilding the virtual environment (.venv)'
    uv venv --clear --python 3.12
    if ($LASTEXITCODE -ne 0) { throw 'uv venv failed' }
}

Write-Step 'Installing dependencies (uv sync)'
uv sync --extra dev
if ($LASTEXITCODE -ne 0) { throw 'uv sync failed' }

# --- 2. UI dependencies ----------------------------------------------------
$uiDir = Join-Path $RepoRoot 'packages\mv-ui'
if (-not (Test-Path -LiteralPath (Join-Path $uiDir 'node_modules'))) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw 'npm/Node is not installed. Install Node 20+ to run the UI.'
    }
    Write-Step 'Installing UI dependencies (npm install)'
    Push-Location $uiDir
    try { npm install } finally { Pop-Location }
}

# --- 3. free the ports (idempotent re-run) --------------------------------
Write-Step "Freeing ports $ApiPort / $UiPort"
Reset-Port $ApiPort
Reset-Port $UiPort
Reset-Port 3001
Reset-Port 3002
Start-Sleep -Seconds 1

# --- 4. start the API window ----------------------------------------------
# Resolve the Operator token: explicit param > .env > freshly generated. The
# generated token is persisted to the git-ignored .env so the Kill / Adopt
# buttons keep working across restarts (open .env to copy the value).
$weakTokens = @('', 'paper-secret', 'change-me-operator-token')
if ($OperatorToken -in $weakTokens) { $OperatorToken = Get-DotEnvValue 'MV_OPERATOR_TOKEN' }
if (-not $OperatorToken -or ($OperatorToken -in $weakTokens)) {
    $OperatorToken = New-OperatorToken
    Set-DotEnvValue 'MV_OPERATOR_TOKEN' $OperatorToken
    Write-Host 'Generated a random MV_OPERATOR_TOKEN and stored it in .env (guards Kill / Adopt / graduate; open .env to copy it).' -ForegroundColor Green
}
$agentFlag = if ($Agents) { ' --agents' } else { '' }
$mode = if ($Agents) { 'AI agents' } else { 'ensemble' }
Write-Step "Starting API (mv-serve, $mode, continuous: re-runs every ${IntervalSeconds}s on $Timeframe bars) on :$ApiPort"
Start-ServerWindow @"
`$host.UI.RawUI.WindowTitle = 'Market Viceroy - API (mv-serve, watch)'
Set-Location '$RepoRoot'
`$env:MV_OPERATOR_TOKEN = '$OperatorToken'
`$env:MV_UI_ORIGIN = 'http://localhost:$UiPort'
`$env:UV_LINK_MODE = 'copy'
uv run mv-serve --host 127.0.0.1 --port $ApiPort --watch --interval $IntervalSeconds --timeframe $Timeframe$agentFlag
"@

# --- 5. wait for the API (it runs a paper session first, then serves) -----
Write-Host -NoNewline 'Waiting for the API '
$apiUp = $false
for ($i = 0; $i -lt 90; $i++) {
    try {
        if ((Invoke-RestMethod "http://127.0.0.1:$ApiPort/api/v1/health" -TimeoutSec 2).status -eq 'ok') {
            $apiUp = $true; break
        }
    }
    catch { }
    Start-Sleep -Seconds 2; Write-Host -NoNewline '.'
}
Write-Host ''
if ($apiUp) { Write-Host 'API is up.' -ForegroundColor Green }
else { Write-Warning 'API not healthy yet - check its window; the UI may show "Degraded" until it is.' }

# --- 6. start the UI window ------------------------------------------------
Write-Step "Starting UI (npm run dev) on :$UiPort"
Start-ServerWindow @"
`$host.UI.RawUI.WindowTitle = 'Market Viceroy - UI (npm run dev)'
Set-Location '$uiDir'
`$env:NEXT_PUBLIC_API_URL = 'http://127.0.0.1:$ApiPort'
npm run dev
"@

# --- 7. wait for the UI ----------------------------------------------------
Write-Host -NoNewline 'Waiting for the UI '
$uiUp = $false
for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-WebRequest "http://localhost:$UiPort" -TimeoutSec 2 -UseBasicParsing | Out-Null; $uiUp = $true; break }
    catch { }
    Start-Sleep -Seconds 2; Write-Host -NoNewline '.'
}
Write-Host ''
if ($uiUp) { Write-Host 'UI is up.' -ForegroundColor Green }

# --- 8. open the deck in Edge InPrivate (ad-blocker-free) -----------------
Write-Step 'Opening the Command Deck in Edge InPrivate'
$edge = (Get-Command msedge -ErrorAction SilentlyContinue).Source
if (-not $edge) {
    foreach ($p in @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
            "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe")) {
        if (Test-Path -LiteralPath $p) { $edge = $p; break }
    }
}
if ($edge) {
    Start-Process $edge -ArgumentList '--inprivate', "http://localhost:$UiPort"
}
else {
    Start-Process "http://localhost:$UiPort"
    Write-Warning 'Edge not found - opened your default browser. If the deck shows "Degraded", pause your ad blocker for localhost.'
}

Write-Host ''
Write-Host "Command Deck : http://localhost:$UiPort   (Edge InPrivate)" -ForegroundColor Green
Write-Host "API health   : http://127.0.0.1:$ApiPort/api/v1/health" -ForegroundColor Green
Write-Host "Continuous   : the API re-runs every ${IntervalSeconds}s on $Timeframe bars - equity, positions, decisions and logs keep updating." -ForegroundColor DarkGray
Write-Host 'Two server windows are now running (API + UI). Close them to stop; re-run this script to restart.' -ForegroundColor DarkGray
