#!/usr/bin/env python3
"""Generate visualizations from benchmark results."""

import argparse
import sys
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from benchmarks.metrics.analyzer import BenchmarkAnalyzer

try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    import numpy as np
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False
    print("Warning: matplotlib and seaborn not installed. Install with:")
    print("  pip install matplotlib seaborn")


def plot_success_rates(analyzer: BenchmarkAnalyzer, output_dir: Path):
    """Plot success rates by framework."""
    if not PLOTTING_AVAILABLE:
        return

    frameworks = list(analyzer.framework_results.keys())
    success_rates = [analyzer.get_success_rate(fw) for fw in frameworks]

    plt.figure(figsize=(10, 6))
    sns.barplot(x=frameworks, y=success_rates)
    plt.ylabel("Success Rate")
    plt.title("Task Success Rate by Framework")
    plt.ylim(0, 1.0)
    plt.tight_layout()
    plt.savefig(output_dir / "success_rates.png", dpi=300)
    plt.close()

    print(f"✓ Generated success_rates.png")


def plot_completion_times(analyzer: BenchmarkAnalyzer, output_dir: Path):
    """Plot completion time distributions."""
    if not PLOTTING_AVAILABLE:
        return

    plt.figure(figsize=(12, 6))

    frameworks = list(analyzer.framework_results.keys())
    data = []
    labels = []

    for framework in frameworks:
        times = [
            r.get('completion_time_seconds', 0)
            for r in analyzer.framework_results[framework]
        ]
        if times:
            data.append(times)
            labels.append(framework)

    plt.boxplot(data, labels=labels)
    plt.ylabel("Completion Time (seconds)")
    plt.title("Task Completion Time Distribution by Framework")
    plt.tight_layout()
    plt.savefig(output_dir / "completion_times.png", dpi=300)
    plt.close()

    print(f"✓ Generated completion_times.png")


def plot_cost_comparison(analyzer: BenchmarkAnalyzer, output_dir: Path):
    """Plot cost comparison."""
    if not PLOTTING_AVAILABLE:
        return

    frameworks = list(analyzer.framework_results.keys())
    costs = []

    for framework in frameworks:
        total_cost = sum(
            r.get('estimated_cost_usd', 0)
            for r in analyzer.framework_results[framework]
        )
        costs.append(total_cost)

    plt.figure(figsize=(10, 6))
    sns.barplot(x=frameworks, y=costs)
    plt.ylabel("Total Cost (USD)")
    plt.title("Total Cost by Framework")
    plt.tight_layout()
    plt.savefig(output_dir / "cost_comparison.png", dpi=300)
    plt.close()

    print(f"✓ Generated cost_comparison.png")


def plot_category_performance(analyzer: BenchmarkAnalyzer, output_dir: Path):
    """Plot performance by task category."""
    if not PLOTTING_AVAILABLE:
        return

    category_analysis = analyzer.get_task_category_analysis()

    if not category_analysis:
        return

    # Success rates by category
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    categories = list(category_analysis.keys())
    frameworks = list(analyzer.framework_results.keys())

    # Success rate plot
    width = 0.2
    x = np.arange(len(categories))

    for i, framework in enumerate(frameworks):
        rates = []
        for category in categories:
            fw_data = category_analysis[category]['frameworks'].get(framework, {})
            rates.append(fw_data.get('success_rate', 0))

        ax1.bar(x + i * width, rates, width, label=framework)

    ax1.set_xlabel('Task Category')
    ax1.set_ylabel('Success Rate')
    ax1.set_title('Success Rate by Category and Framework')
    ax1.set_xticks(x + width * (len(frameworks) - 1) / 2)
    ax1.set_xticklabels(categories)
    ax1.legend()
    ax1.set_ylim(0, 1.0)

    # Average time plot
    for i, framework in enumerate(frameworks):
        times = []
        for category in categories:
            fw_data = category_analysis[category]['frameworks'].get(framework, {})
            times.append(fw_data.get('avg_time', 0))

        ax2.bar(x + i * width, times, width, label=framework)

    ax2.set_xlabel('Task Category')
    ax2.set_ylabel('Average Time (seconds)')
    ax2.set_title('Average Completion Time by Category')
    ax2.set_xticks(x + width * (len(frameworks) - 1) / 2)
    ax2.set_xticklabels(categories)
    ax2.legend()

    plt.tight_layout()
    plt.savefig(output_dir / "category_performance.png", dpi=300)
    plt.close()

    print(f"✓ Generated category_performance.png")


def main():
    parser = argparse.ArgumentParser(description="Visualize benchmark results")

    parser.add_argument(
        "results_dir",
        help="Directory containing benchmark results"
    )

    parser.add_argument(
        "--output",
        "-o",
        default="benchmarks/figures",
        help="Output directory for figures"
    )

    args = parser.parse_args()

    if not PLOTTING_AVAILABLE:
        print("Error: matplotlib and seaborn are required for visualization")
        print("Install with: pip install matplotlib seaborn")
        sys.exit(1)

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load results
    analyzer = BenchmarkAnalyzer(args.results_dir)
    print(f"Loading results from {args.results_dir}...")
    analyzer.load_results()

    print(f"Loaded {len(analyzer.task_results)} task results")
    print(f"Frameworks: {', '.join(analyzer.framework_results.keys())}")
    print()

    # Generate visualizations
    print("Generating visualizations...")

    plot_success_rates(analyzer, output_dir)
    plot_completion_times(analyzer, output_dir)
    plot_cost_comparison(analyzer, output_dir)
    plot_category_performance(analyzer, output_dir)

    print(f"\n✓ All visualizations saved to {output_dir}")


if __name__ == "__main__":
    main()
