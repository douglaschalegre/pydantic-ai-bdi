#!/usr/bin/env python3
"""Generate usability assessment report for frameworks."""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from benchmarks.usability.ease_of_use import create_standard_assessments


def main():
    parser = argparse.ArgumentParser(description="Generate usability report")

    parser.add_argument(
        "--output",
        "-o",
        default="usability_report.md",
        help="Output file for report"
    )

    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("FRAMEWORK1", "FRAMEWORK2"),
        help="Compare two specific frameworks"
    )

    args = parser.parse_args()

    # Create standard assessments
    evaluator = create_standard_assessments()

    if args.compare:
        # Compare two frameworks
        fw1, fw2 = args.compare
        print(f"Comparing {fw1} vs {fw2}")
        print()

        comparison = evaluator.compare_frameworks(fw1, fw2)

        if "error" in comparison:
            print(f"Error: {comparison['error']}")
            sys.exit(1)

        print(f"Overall Scores:")
        print(f"  {fw1}: {comparison['overall_scores'][fw1]:.1f}/10.0")
        print(f"  {fw2}: {comparison['overall_scores'][fw2]:.1f}/10.0")
        print(f"  Winner: {comparison['winner']}")
        print()

        print("Dimension Comparison:")
        for dimension, data in comparison['dimension_comparison'].items():
            print(f"\n  {dimension.replace('_', ' ').title()}:")
            print(f"    {fw1}: {data[fw1]:.1f}")
            print(f"    {fw2}: {data[fw2]:.1f}")
            print(f"    Better: {data['better']}")

    else:
        # Generate full report
        print("Generating usability assessment report...")

        report = evaluator.generate_report()

        with open(args.output, 'w') as f:
            f.write(report)

        print(f"✓ Report saved to {args.output}")

        # Print summary
        print("\nUsability Rankings:")
        assessments = sorted(
            evaluator.assessments.items(),
            key=lambda x: x[1].get_overall_score(),
            reverse=True
        )

        for rank, (framework, assessment) in enumerate(assessments, 1):
            print(f"{rank}. {framework}: {assessment.get_overall_score():.1f}/10.0")


if __name__ == "__main__":
    main()
