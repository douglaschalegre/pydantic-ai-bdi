from pathlib import Path

import pytest

from scripts.release import next_version, select_release_kind, update_version


@pytest.mark.parametrize(
    ("current", "kind", "expected"),
    [
        ("0.1.0", "patch", "0.1.1"),
        ("0.1.9", "minor", "0.2.0"),
        ("0.9.9", "major", "1.0.0"),
    ],
)
def test_next_version(current: str, kind: str, expected: str) -> None:
    assert next_version(current, kind) == expected


def test_select_release_kind_ignores_unrelated_labels() -> None:
    assert select_release_kind(["documentation", "release:minor"]) == "minor"


@pytest.mark.parametrize(
    "labels",
    [[], ["documentation"], ["release:patch", "release:major"]],
)
def test_select_release_kind_requires_exactly_one_label(labels: list[str]) -> None:
    with pytest.raises(ValueError, match="exactly one release label"):
        select_release_kind(labels)


def test_update_version_updates_both_sources(tmp_path: Path) -> None:
    (tmp_path / "voluntas").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "voluntas"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (tmp_path / "voluntas" / "__init__.py").write_text(
        '__version__ = "0.1.0"\n', encoding="utf-8"
    )
    assert update_version(tmp_path, "patch") == "0.1.1"
    assert 'version = "0.1.1"' in (tmp_path / "pyproject.toml").read_text()
    assert '__version__ = "0.1.1"' in (
        tmp_path / "voluntas" / "__init__.py"
    ).read_text()
