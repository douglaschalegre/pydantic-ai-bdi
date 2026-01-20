#!/usr/bin/env python3
"""Command-line script for analyzing benchmark results."""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from benchmarks.metrics.analyzer import BenchmarkAnalyzer


def main():
    parser = argparse.ArgumentParser(description="Analyze benchmark results")

    parser.add_argument(
        "results_dir",
        help="Directory containing benchmark results"
    )

    parser.add_argument(
        "--output",
        "-o",
        help="Output file for report (default: stdout)"
    )

    parser.add_argument(
        "--csv",
        help="Export results to CSV file"
    )

    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("FRAMEWORK1", "FRAMEWORK2"),
        help="Compare two specific frameworks"
    )

    parser.add_argument(
        "--metric",
        default="completion_time_seconds",
        help="Metric to compare (default: completion_time_seconds)"
    )

    args = parser.parse_args()

    # Create analyzer
    analyzer = BenchmarkAnalyzer(args.results_dir)

    print(f"Loading results from {args.results_dir}...")
    analyzer.load_results()

    print(f"Loaded {len(analyzer.task_results)} task results")
    print(f"Frameworks: {', '.join(analyzer.framework_results.keys())}")
    print()

    # Generate report
    if args.compare:
        fw1, fw2 = args.compare
        print(f"Comparing {fw1} vs {fw2} on {args.metric}")
        print()

        comparison = analyzer.compare_frameworks(fw1, fw2, args.metric)
        print(comparison.get_interpretation())
        print()
        print(f"Statistics:")
        print(f"  {fw1}: mean={comparison.mean1:.2f}, std={comparison.std1:.2f}")
        print(f"  {fw2}: mean={comparison.mean2:.2f}, std={comparison.std2:.2f}")

        if comparison.p_value:
            print(f"  p-value: {comparison.p_value:.4f}")
            print(f"  Significant: {comparison.significant}")

        if comparison.cohens_d:
            print(f"  Cohen's d: {comparison.cohens_d:.2f}")

    else:
        report = analyzer.generate_report(args.output)

        if args.output:
            print(f"Report saved to {args.output}")
        else:
            print(report)

    # Export CSV if requested
    if args.csv:
        analyzer.export_csv(args.csv)
        print(f"\nResults exported to {args.csv}")


if __name__ == "__main__":
    main()
