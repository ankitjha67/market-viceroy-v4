# Install AlphaKit sub-packages from a GitHub tag (PowerShell).
#
# Usage:
#   .\scripts\install_from_git.ps1 -Tag v0.1.1
#   .\scripts\install_from_git.ps1 -Tag v0.1.1 -Families @("core", "bridges", "strategies-trend")

param(
    [Parameter(Mandatory=$true)]
    [string]$Tag,

    [string[]]$Families = @(
        "core",
        "data",
        "bridges",
        "strategies-trend",
        "strategies-meanrev",
        "strategies-carry",
        "strategies-value",
        "strategies-volatility",
        "strategies-rates",
        "strategies-commodity",
        "strategies-options",
        "bench"
    )
)

$ErrorActionPreference = "Stop"
$Repo = "https://github.com/ankitjha67/alphakit.git"

Write-Host "Installing $($Families.Count) AlphaKit packages from tag $Tag"
Write-Host "================================================================"

foreach ($pkg in $Families) {
    Write-Host "  Installing alphakit-$pkg..."
    pip install "alphakit-$pkg @ git+$Repo@$Tag#subdirectory=packages/alphakit-$pkg" --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install alphakit-$pkg"
        exit 1
    }
}

Write-Host "================================================================"
Write-Host "Done. Verify with:"
Write-Host '  python -c "from alphakit.core.protocols import StrategyProtocol; print(''OK'')"'
