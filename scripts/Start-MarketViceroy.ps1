#Requires -Version 5.1
<#
.SYNOPSIS
  One-shot operator launcher for Market Viceroy v4. Sets up the workspace and
  infra, collects API keys (the only thing you type), then runs paper trades,
  the Command Deck UI, backtests, the agent pipeline, and post-mortems from a
  menu.

.DESCRIPTION
  Paper-first. Crypto market data needs no key, so the platform runs with zero
  input -- every other data source is optional (press Enter to skip or keep the
  current value). Secrets are written ONLY to the git-ignored .env (never to
  code) and exported into the child processes so the adapters pick them up.
  Nothing here ever places a real-money order.

.PARAMETER SkipSetup
  Skip uv sync / docker compose / migrations (assume already done).

.PARAMETER SkipKeys
  Skip the API-key prompts and use the existing .env as-is.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\Start-MarketViceroy.ps1

.NOTES
  Re-running is safe: uv sync and docker compose are idempotent, and Enter at a
  key prompt keeps whatever is already in .env.
#>
[CmdletBinding()]
param(
    [switch]$SkipSetup,
    [switch]$SkipKeys
)

$ErrorActionPreference = 'Stop'
$RepoRoot   = Split-Path -Parent $PSScriptRoot
$EnvFile    = Join-Path $RepoRoot '.env'
$EnvExample = Join-Path $RepoRoot '.env.example'
$ApiUrl     = 'http://127.0.0.1:8000'
$UiUrl      = 'http://localhost:3000'

# Data sources, in failover priority. Each lists the .env var(s) it needs and
# where to obtain them. Crypto has no keys (public data). The first key of a
# source is its trigger: leave it blank to skip the whole source.
$Sources = @(
    @{ Name = 'Crypto  (Binance / Kraken / Coinbase)'; Url = 'public OHLCV -- no key required'; Keys = @() }
    @{ Name = 'FRED    (macro series for the backtest gate)'; Url = 'https://fred.stlouisfed.org/docs/api/api_key.html  (runtime input only, never trained on)'; Keys = @('FRED_API_KEY') }
    @{ Name = 'Finnhub (US equities, primary)';        Url = 'https://finnhub.io';                  Keys = @('FINNHUB_API_KEY') }
    @{ Name = 'Alpaca  (US equities, fallback)';       Url = 'https://alpaca.markets  (free paper account)'; Keys = @('ALPACA_API_KEY', 'ALPACA_API_SECRET') }
    @{ Name = 'Dhan    (India equities, PRIMARY)';     Url = 'https://dhanhq.co  -> DhanHQ API';     Keys = @('DHAN_ACCESS_TOKEN', 'DHAN_CLIENT_ID') }
    @{ Name = 'Upstox  (India fallback 1)';            Url = 'https://upstox.com/developer/';        Keys = @('UPSTOX_ACCESS_TOKEN') }
    @{ Name = 'Kotak   (India fallback 2, Neo API)';   Url = 'Kotak Neo API portal';                 Keys = @('KOTAK_ACCESS_TOKEN', 'KOTAK_CONSUMER_KEY') }
    @{ Name = 'Zerodha (India fallback 3, Kite)';      Url = 'https://kite.trade  (internal-use only, no data redistribution)'; Keys = @('ZERODHA_API_KEY', 'ZERODHA_ACCESS_TOKEN') }
    @{ Name = 'AngelOne(India fallback 4, SmartAPI)';  Url = 'https://smartapi.angelbroking.com';    Keys = @('ANGELONE_API_KEY', 'ANGELONE_ACCESS_TOKEN') }
    @{ Name = 'EIA     (energy data)';                 Url = 'https://www.eia.gov/opendata/';        Keys = @('EIA_API_KEY') }
    @{ Name = 'Polygon (market data)';                 Url = 'https://polygon.io';                   Keys = @('POLYGON_API_KEY') }
    @{ Name = 'Anthropic (optional cloud LLM for agents)'; Url = 'https://console.anthropic.com';    Keys = @('ANTHROPIC_API_KEY') }
)

function Write-Section {
    param([string]$Text)
    $bar = ''.PadRight(72, '=')
    Write-Host ''
    Write-Host $bar -ForegroundColor DarkCyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host $bar -ForegroundColor DarkCyan
}

function Test-Cmd {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

# Read a secret without echoing it to the screen; returns plaintext ('' if blank).
function Read-Secret {
    param([string]$Prompt)
    $secure = Read-Host -Prompt $Prompt -AsSecureString
    if ($null -eq $secure -or $secure.Length -eq 0) { return '' }
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

# Set KEY=VALUE in .env, replacing a commented or existing line in place;
# appends if absent. Writes UTF-8 without a BOM so dotenv/pydantic parse cleanly.
function Set-EnvVar {
    param([string]$Key, [string]$Value)
    $lines = @()
    if (Test-Path -LiteralPath $EnvFile) { $lines = @(Get-Content -LiteralPath $EnvFile) }
    $pattern = "^\s*#?\s*$([regex]::Escape($Key))\s*="
    $newLine = "$Key=$Value"
    $out = New-Object System.Collections.Generic.List[string]
    $found = $false
    foreach ($line in $lines) {
        if (-not $found -and $line -match $pattern) { $out.Add($newLine); $found = $true }
        else { $out.Add($line) }
    }
    if (-not $found) { $out.Add($newLine) }
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($EnvFile, $out, $utf8NoBom)
}

# Current value of an uncommented KEY in .env, or $null.
function Get-EnvVar {
    param([string]$Key)
    if (-not (Test-Path -LiteralPath $EnvFile)) { return $null }
    foreach ($line in (Get-Content -LiteralPath $EnvFile)) {
        if ($line.Trim().StartsWith('#')) { continue }
        if ($line -match "^\s*$([regex]::Escape($Key))\s*=(.*)$") { return $Matches[1].Trim() }
    }
    return $null
}

# Load .env into the current process environment so child `uv run` processes see
# the broker/market keys (the adapters read os.environ directly) and the
# Operator token. Harmless for the pydantic Settings path (it reads .env too).
function Import-DotEnv {
    if (-not (Test-Path -LiteralPath $EnvFile)) { return }
    foreach ($line in (Get-Content -LiteralPath $EnvFile)) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith('#')) { continue }
        $idx = $t.IndexOf('=')
        if ($idx -lt 1) { continue }
        $k = $t.Substring(0, $idx).Trim()
        $v = $t.Substring($idx + 1).Trim()
        if ($v.Length -ge 2) {
            $q = $v[0]
            if (($q -eq '"' -or $q -eq "'") -and $v[$v.Length - 1] -eq $q) {
                $v = $v.Substring(1, $v.Length - 2)
            }
        }
        Set-Item -Path ("Env:" + $k) -Value $v
    }
}

function New-OperatorToken {
    $bytes = New-Object 'System.Byte[]' 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return (([System.BitConverter]::ToString($bytes)) -replace '-', '').ToLower()
}

function Invoke-KeyPrompts {
    Write-Section 'API keys  (optional -- Enter to skip a source or keep the current value)'
    Write-Host 'Keys are written only to .env (git-ignored) and never echoed. Crypto needs none.' -ForegroundColor DarkGray
    foreach ($src in $Sources) {
        if ($src.Keys.Count -eq 0) {
            Write-Host ("  - {0}  (no key needed)" -f $src.Name) -ForegroundColor DarkGray
            continue
        }
        Write-Host ''
        Write-Host ("  {0}" -f $src.Name) -ForegroundColor White
        Write-Host ("    where: {0}" -f $src.Url) -ForegroundColor DarkGray
        $first = $src.Keys[0]
        $existing = Get-EnvVar $first
        $hint = if ($existing) { 'Enter to keep current' } else { 'Enter to skip' }
        $val = Read-Secret ("    {0} ({1})" -f $first, $hint)
        if (-not $val) { Write-Host '    (unchanged)' -ForegroundColor DarkGray; continue }
        Set-EnvVar $first $val
        Write-Host ("    {0} set" -f $first) -ForegroundColor Green
        foreach ($k in ($src.Keys | Select-Object -Skip 1)) {
            $v2 = Read-Secret ("    {0}" -f $k)
            if ($v2) {
                Set-EnvVar $k $v2
                Write-Host ("    {0} set" -f $k) -ForegroundColor Green
            }
            else {
                Write-Host ("    {0} left blank (this source needs it to work)" -f $k) -ForegroundColor DarkYellow
            }
        }
    }
}

function Start-CommandDeck {
    param([switch]$Agents)
    $uiDir = Join-Path $RepoRoot 'packages\mv-ui'
    $env:NEXT_PUBLIC_API_URL = $ApiUrl   # inherited by the spawned UI process

    $serveArgs = @('run', 'mv-serve')
    if ($Agents) { $serveArgs += '--agents' }
    Write-Host 'Starting the Command Deck API (mv-serve) in a new window...' -ForegroundColor Yellow
    Write-Host '  It runs a paper session over live bars first (~30-60s), then serves.' -ForegroundColor DarkGray
    Start-Process -FilePath 'uv' -ArgumentList $serveArgs -WorkingDirectory $RepoRoot

    if (Test-Cmd 'npm') {
        if (-not (Test-Path -LiteralPath (Join-Path $uiDir 'node_modules'))) {
            Write-Host 'Installing UI dependencies (first run only: npm install)...' -ForegroundColor Yellow
            Push-Location $uiDir
            try { npm install } finally { Pop-Location }
        }
        Write-Host 'Starting the Command Deck UI (npm run dev) in a new window...' -ForegroundColor Yellow
        Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'npm', 'run', 'dev' -WorkingDirectory $uiDir
        Start-Sleep -Seconds 5
        Start-Process $UiUrl
        Write-Host ("Command Deck -> {0}   (API -> {1})" -f $UiUrl, $ApiUrl) -ForegroundColor Green
        Write-Host 'The kill-switch is on the deck (uses your MV_OPERATOR_TOKEN). Restart mv-serve to refresh.' -ForegroundColor DarkGray
    }
    else {
        Write-Warning 'Node.js/npm not found -- install Node 20+ to run the UI. Serving the API only.'
        Write-Host ("API -> {0}/api/v1/health" -f $ApiUrl) -ForegroundColor Green
    }
}

# ---------------------------------------------------------------------------
Push-Location $RepoRoot
try {
    Write-Section 'Market Viceroy v4 -- operator launcher'
    Write-Host 'Paper-first. The agent never places a real-money order. Ctrl+C aborts.' -ForegroundColor DarkGray

    if (-not (Test-Cmd 'uv')) {
        throw 'uv is not installed. Install it from https://docs.astral.sh/uv/ and re-run.'
    }
    $haveDocker = Test-Cmd 'docker'

    if (-not (Test-Path -LiteralPath $EnvFile)) {
        Copy-Item -LiteralPath $EnvExample -Destination $EnvFile
        Write-Host 'Created .env from .env.example' -ForegroundColor Green
    }

    # An Operator token is required by mv-serve and guards kill/reset/graduate.
    # Generate a strong random one once so the user never has to think about it.
    $tok = Get-EnvVar 'MV_OPERATOR_TOKEN'
    if (-not $tok -or $tok -eq 'change-me-operator-token') {
        Set-EnvVar 'MV_OPERATOR_TOKEN' (New-OperatorToken)
        Write-Host 'Generated a random MV_OPERATOR_TOKEN (guards kill / reset / graduate).' -ForegroundColor Green
    }

    if (-not $SkipSetup) {
        Write-Section 'Setup'
        Write-Host '-> uv sync --extra dev' -ForegroundColor Yellow
        uv sync --extra dev
        if ($LASTEXITCODE -ne 0) { throw 'uv sync failed' }

        if ($haveDocker) {
            Write-Host '-> docker compose up -d   (ClickHouse + Postgres + Redis)' -ForegroundColor Yellow
            docker compose up -d
            if ($LASTEXITCODE -ne 0) {
                Write-Warning 'docker compose failed. Is Docker Desktop running? Redis is required for the kill-switch.'
            }
            else {
                Write-Host '-> applying Postgres migrations (mv-migrate)' -ForegroundColor Yellow
                Import-DotEnv
                $migrated = $false
                for ($i = 1; $i -le 5; $i++) {
                    uv run mv-migrate
                    if ($LASTEXITCODE -eq 0) { $migrated = $true; break }
                    Write-Host ("   Postgres not ready yet -- retrying ({0}/5)" -f $i) -ForegroundColor DarkYellow
                    Start-Sleep -Seconds 3
                }
                if (-not $migrated) { Write-Warning 'mv-migrate did not succeed yet; re-run later once Postgres is up.' }
            }
        }
        else {
            Write-Warning 'Docker not found. Skipping infra + migrations.'
            Write-Host '  Paper trading still works (zero-infra: an in-process kill-switch).' -ForegroundColor DarkGray
            Write-Host '  Install Docker Desktop for the shared kill-switch, journal persistence, and the full stack.' -ForegroundColor DarkGray
        }
    }

    if (-not $SkipKeys) { Invoke-KeyPrompts }

    # Make every key effective for the child processes launched from the menu.
    Import-DotEnv

    Write-Host ''
    Write-Host 'Setup complete. Crypto paper trading works now with no keys.' -ForegroundColor Green

    do {
        Write-Section 'Run  (pick one)'
        Write-Host '  1) Paper trade -- real-time crypto (deterministic ensemble)'
        Write-Host '  2) Paper trade -- real-time crypto (AI agent pipeline)'
        Write-Host '  3) Command Deck UI + live P&L (ensemble)'
        Write-Host '  4) Command Deck UI + live P&L (AI agents)'
        Write-Host '  5) Backtest / validation gate'
        Write-Host '  6) Agent reasoning transcript (glass box)'
        Write-Host '  7) Post-mortem -- how agents improve strategies'
        Write-Host '  8) Arbitrage monitor (after-cost, R/A/G)'
        Write-Host '  9) Trip the kill-switch (halt all trading)'
        Write-Host '  K) Re-enter API keys'
        Write-Host '  Q) Quit'
        $choice = (Read-Host 'Select').Trim().ToUpper()
        switch ($choice) {
            '1' { uv run mv-paper }
            '2' { uv run mv-paper --agents }
            '3' { Start-CommandDeck }
            '4' { Start-CommandDeck -Agents }
            '5' { uv run python scripts/run_gate.py }
            '6' { uv run python scripts/run_agents.py }
            '7' { uv run python scripts/run_postmortem.py }
            '8' { uv run python scripts/run_arbitrage.py }
            '9' { uv run mv-kill 'operator halt via launcher' }
            'K' { Invoke-KeyPrompts; Import-DotEnv }
            'Q' { }
            default { Write-Host 'Unknown choice.' -ForegroundColor DarkYellow }
        }
    } while ($choice -ne 'Q')

    Write-Host ''
    Write-Host 'Done. Re-run any time; see docs/RUNBOOK.md for the full guide.' -ForegroundColor Green
}
finally {
    Pop-Location
}
