#!/bin/bash
# Convenience script for installing benchmark dependencies
# Usage: ./install-benchmarks.sh [group]
# Groups: benchmark, frameworks, viz, benchmark-all (default)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default to all benchmark dependencies
GROUP="${1:-benchmark-all}"

echo "======================================"
echo "Installing Benchmark Dependencies"
echo "======================================"
echo ""
echo "Project root: $PROJECT_ROOT"
echo "Dependency group: $GROUP"
echo ""

cd "$PROJECT_ROOT"

# Check if uv is available
if command -v uv &> /dev/null; then
    echo "Using uv (fast installer)..."
    uv pip install -e ".[$GROUP]"
else
    echo "uv not found, using pip..."
    echo "Tip: Install uv for faster installations: pip install uv"
    pip install -e ".[$GROUP]"
fi

echo ""
echo "======================================"
echo "Installation Complete!"
echo "======================================"
echo ""
echo "Available commands:"
echo "  benchmark-run       - Run benchmarks"
echo "  benchmark-analyze   - Analyze results"
echo "  benchmark-viz       - Generate visualizations"
echo "  experiment-run      - Run participant experiments"
echo ""
echo "Example usage:"
echo "  benchmark-run --framework bdi --category simple"
echo "  experiment-run --participant 1"
echo ""
