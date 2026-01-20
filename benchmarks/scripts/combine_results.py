#!/usr/bin/env python3
"""Combine multiple benchmark runs into a single directory."""

import argparse
import json
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Combine benchmark results")

    parser.add_argument(
        "results_dir",
        help="Directory containing multiple run directories"
    )

    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output directory for combined results"
    )

    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Combining results from {results_dir} to {output_dir}")

    # Find all JSON files in subdirectories
    json_files = list(results_dir.glob("**/*.json"))

    print(f"Found {len(json_files)} result files")

    # Copy all JSON files to output directory
    copied = 0
    for json_file in json_files:
        # Skip if in output directory
        if str(output_dir) in str(json_file):
            continue

        # Create unique name if needed
        dest_name = json_file.name
        dest_path = output_dir / dest_name

        # Add prefix if duplicate
        counter = 1
        while dest_path.exists():
            stem = json_file.stem
            dest_name = f"{stem}_{counter}{json_file.suffix}"
            dest_path = output_dir / dest_name
            counter += 1

        shutil.copy(json_file, dest_path)
        copied += 1

    print(f"✓ Copied {copied} files to {output_dir}")


if __name__ == "__main__":
    main()
