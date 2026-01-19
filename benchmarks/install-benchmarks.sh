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
echo "This will install:"
echo "  1. BDI Agent Framework (pydantic-ai, fastapi, etc.)"
echo "  2. Benchmark tools (scipy, numpy, psutil)"
if [ "$GROUP" = "benchmark-all" ] || [ "$GROUP" = "frameworks" ]; then
    echo "  3. Agent Frameworks (LangGraph, CrewAI)"
fi
if [ "$GROUP" = "benchmark-all" ] || [ "$GROUP" = "viz" ]; then
    echo "  4. Visualization tools (matplotlib, seaborn)"
fi
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
echo "Verifying installation..."
echo ""

# Verify core dependencies
python -c "import bdi; print('✓ BDI Agent Framework')" 2>/dev/null || echo "✗ BDI Agent Framework (FAILED)"
python -c "import pydantic_ai; print('✓ Pydantic AI')" 2>/dev/null || echo "✗ Pydantic AI (FAILED)"
python -c "import scipy; print('✓ SciPy (statistics)')" 2>/dev/null || echo "✗ SciPy"
python -c "import numpy; print('✓ NumPy')" 2>/dev/null || echo "✗ NumPy"

if [ "$GROUP" = "benchmark-all" ] || [ "$GROUP" = "frameworks" ]; then
    python -c "import langgraph; print('✓ LangGraph')" 2>/dev/null || echo "✗ LangGraph"
    python -c "import crewai; print('✓ CrewAI')" 2>/dev/null || echo "✗ CrewAI"
fi

if [ "$GROUP" = "benchmark-all" ] || [ "$GROUP" = "viz" ]; then
    python -c "import matplotlib; print('✓ Matplotlib')" 2>/dev/null || echo "✗ Matplotlib"
fi

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
echo "Test your setup:"
echo "  python benchmarks/experiments/bdi/TEMPLATE.py"
echo ""
