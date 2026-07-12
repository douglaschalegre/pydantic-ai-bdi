"""Select a release type and update Voluntas' version files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path

RELEASE_LABELS = {
    "release:patch": "patch",
    "release:minor": "minor",
    "release:major": "major",
}
SEMVER_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
PROJECT_VERSION_PATTERN = re.compile(r'(?m)^version = "([^"]+)"$')
PACKAGE_VERSION_PATTERN = re.compile(r'(?m)^__version__ = "([^"]+)"$')


def select_release_kind(labels: Sequence[str]) -> str:
    """Return the release kind represented by exactly one release label."""
    matches = [RELEASE_LABELS[label] for label in labels if label in RELEASE_LABELS]
    if len(matches) != 1:
        selected = ", ".join(label for label in labels if label in RELEASE_LABELS)
        raise ValueError(
            "Expected exactly one release label "
            f"({', '.join(RELEASE_LABELS)}); selected: {selected or 'none'}."
        )
    return matches[0]


def next_version(version: str, kind: str) -> str:
    """Increment a strict three-component semantic version."""
    match = SEMVER_PATTERN.fullmatch(version)
    if match is None:
        raise ValueError(f"Version must use MAJOR.MINOR.PATCH format: {version!r}.")
    major, minor, patch = map(int, match.groups())
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    if kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Unknown release kind: {kind!r}.")


def update_version(root: Path, kind: str) -> str:
    """Update pyproject.toml and voluntas.__version__, returning the new version."""
    pyproject_path = root / "pyproject.toml"
    package_path = root / "voluntas" / "__init__.py"
    pyproject = pyproject_path.read_text(encoding="utf-8")
    package = package_path.read_text(encoding="utf-8")
    project_match = PROJECT_VERSION_PATTERN.search(pyproject)
    if project_match is None:
        raise ValueError(f"Could not find project version in {pyproject_path}.")
    project_version = project_match.group(1)
    package_match = PACKAGE_VERSION_PATTERN.search(package)
    if package_match is None:
        raise ValueError(f"Could not find __version__ in {package_path}.")
    package_version = package_match.group(1)
    if project_version != package_version:
        raise ValueError(
            "Version mismatch before release: "
            f"pyproject.toml={project_version}, voluntas.__version__={package_version}."
        )

    version = next_version(project_version, kind)
    updated_pyproject, project_replacements = PROJECT_VERSION_PATTERN.subn(
        f'version = "{version}"', pyproject, count=1
    )
    updated_package, package_replacements = PACKAGE_VERSION_PATTERN.subn(
        f'__version__ = "{version}"', package, count=1
    )
    if project_replacements != 1 or package_replacements != 1:
        raise ValueError("Could not update all version declarations.")
    pyproject_path.write_text(updated_pyproject, encoding="utf-8")
    package_path.write_text(updated_package, encoding="utf-8")
    return version


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    select_parser = subparsers.add_parser("select-label")
    select_parser.add_argument("labels_json")
    bump_parser = subparsers.add_parser("bump")
    bump_parser.add_argument("kind", choices=("patch", "minor", "major"))
    bump_parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "select-label":
            labels = json.loads(args.labels_json)
            if not isinstance(labels, list) or not all(isinstance(label, str) for label in labels):
                raise ValueError("PR labels must be a JSON array of strings.")
            print(select_release_kind(labels))
        else:
            print(update_version(args.root.resolve(), args.kind))
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"release error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
