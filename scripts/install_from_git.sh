#!/usr/bin/env bash
# Install AlphaKit sub-packages from a GitHub tag.
#
# Usage:
#   bash scripts/install_from_git.sh v0.1.1
#   bash scripts/install_from_git.sh v0.1.1 --families "core bridges strategies-trend"
#
# Installs packages in dependency order so pip can resolve cross-deps
# (e.g. alphakit-strategies-trend depends on alphakit-core).
set -euo pipefail

TAG="${1:?Usage: $0 <tag> [--families \"core bridges ...\"]}"
REPO="https://github.com/ankitjha67/alphakit.git"

# Default: all packages in dependency order
ALL_PKGS=(
    core
    data
    bridges
    strategies-trend
    strategies-meanrev
    strategies-carry
    strategies-value
    strategies-volatility
    strategies-rates
    strategies-commodity
    strategies-options
    bench
)

# Parse optional --families flag
PKGS=("${ALL_PKGS[@]}")
if [[ "${2:-}" == "--families" ]]; then
    IFS=' ' read -ra PKGS <<< "${3:?--families requires a quoted list}"
fi

echo "Installing ${#PKGS[@]} AlphaKit packages from tag ${TAG}"
echo "================================================================"

for pkg in "${PKGS[@]}"; do
    echo "  Installing alphakit-${pkg}..."
    pip install "alphakit-${pkg} @ git+${REPO}@${TAG}#subdirectory=packages/alphakit-${pkg}" \
        --quiet 2>&1 || {
        echo "  ERROR: Failed to install alphakit-${pkg}"
        exit 1
    }
done

echo "================================================================"
echo "Done. Verify with:"
echo "  python -c \"from alphakit.core.protocols import StrategyProtocol; print('OK')\""
