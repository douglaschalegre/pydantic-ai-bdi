#!/bin/bash
# Complete benchmark study script
# This script runs a full benchmark comparison across all frameworks

set -e  # Exit on error

echo "======================================"
echo "BDI Agent Benchmark Study"
echo "======================================"
echo ""

# Configuration
MODEL="openai:gpt-4"
OUTPUT_BASE="benchmarks/results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_DIR="${OUTPUT_BASE}/study_${TIMESTAMP}"

echo "Configuration:"
echo "  Model: $MODEL"
echo "  Output: $RUN_DIR"
echo ""

# Create output directory
mkdir -p "$RUN_DIR"

# Function to run benchmark for a framework
run_framework() {
    local framework=$1
    local category=$2

    echo "----------------------------------------"
    echo "Running $framework - $category tasks"
    echo "----------------------------------------"

    python -m benchmarks.evaluation.runner \
        --framework "$framework" \
        --category "$category" \
        --model "$MODEL" \
        --output "$RUN_DIR/${framework}_${category}" \
        --verbose

    echo ""
}

# Run benchmarks for each framework and category
echo "Phase 1: Running benchmarks..."
echo ""

frameworks=("bdi" "langgraph" "crewai")
categories=("simple" "medium" "complex")

for framework in "${frameworks[@]}"; do
    for category in "${categories[@]}"; do
        run_framework "$framework" "$category"
    done
done

echo "======================================"
echo "Phase 2: Analyzing results..."
echo "======================================"
echo ""

# Combine all results
echo "Combining results..."
python -m benchmarks.scripts.combine_results "$RUN_DIR" --output "$RUN_DIR/combined"

# Generate analysis
echo "Generating analysis report..."
python -m benchmarks.scripts.analyze_results \
    "$RUN_DIR/combined" \
    --output "$RUN_DIR/analysis_report.md" \
    --csv "$RUN_DIR/results.csv"

echo ""
echo "======================================"
echo "Phase 3: Generating visualizations..."
echo "======================================"
echo ""

python -m benchmarks.scripts.visualize_results \
    "$RUN_DIR/combined" \
    --output "$RUN_DIR/figures"

echo ""
echo "======================================"
echo "Phase 4: Usability assessment..."
echo "======================================"
echo ""

python -m benchmarks.scripts.usability_report \
    --output "$RUN_DIR/usability_report.md"

echo ""
echo "======================================"
echo "Study Complete!"
echo "======================================"
echo ""
echo "Results saved to: $RUN_DIR"
echo ""
echo "Generated files:"
echo "  - analysis_report.md    : Statistical analysis"
echo "  - results.csv          : Raw data in CSV format"
echo "  - usability_report.md  : Ease-of-use assessment"
echo "  - figures/             : Visualization charts"
echo ""
echo "View analysis report:"
echo "  cat $RUN_DIR/analysis_report.md"
echo ""
