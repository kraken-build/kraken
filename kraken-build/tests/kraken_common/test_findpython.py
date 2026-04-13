"""Tests for kraken.common.findpython — Python interpreter discovery."""

from __future__ import annotations

import stat
from pathlib import Path

from kraken.common.findpython import _get_candidates


def _make_executable(path: Path) -> None:
    path.touch()
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _candidates_from(bin_dir: Path) -> list[str]:
    """Return candidate names from the given directory, excluding the
    sys.executable fallback that _get_candidates always appends."""
    return [
        Path(c["path"]).name
        for c in _get_candidates(path_list=[str(bin_dir)], check_pyenv=False)
        if Path(c["path"]).parent == bin_dir
    ]


class TestGetCandidatesDeterminism:
    """Verify that _get_candidates yields interpreters in a deterministic order
    regardless of PYTHONHASHSEED / set-iteration randomness."""

    def test_candidates_sorted_by_name(self, tmp_path: Path) -> None:
        """pythonX.Y candidates should appear in version-sorted (ascending) order."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        for name in ["python3.13", "python3.9", "python3.10", "python3.12", "python3.11"]:
            _make_executable(bin_dir / name)

        assert _candidates_from(bin_dir) == [
            "python3.9", "python3.10", "python3.11", "python3.12", "python3.13"
        ]

    def test_category_order_preserved(self, tmp_path: Path) -> None:
        """Generic names should appear before versioned names (py < pythonX < pythonX.Y)."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        for name in ["python3.12", "python3", "python", "python3.11"]:
            _make_executable(bin_dir / name)

        assert _candidates_from(bin_dir) == ["python", "python3", "python3.11", "python3.12"]
