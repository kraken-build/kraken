"""Tests for kraken.common.findpython — Python interpreter discovery."""

from __future__ import annotations

import stat
from pathlib import Path
from unittest.mock import patch

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
    """Verify that _get_candidates yields interpreters in a consistent,
    version-sorted order."""

    def test_candidates_sorted_by_version(self, tmp_path: Path) -> None:
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

    def test_malformed_binary_name_does_not_crash(self, tmp_path: Path) -> None:
        """Binaries like 'python3.' should not crash the sort key."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        for name in ["python3.", "python3.10", "python3.11"]:
            _make_executable(bin_dir / name)

        result = _candidates_from(bin_dir)
        assert "python3.10" in result
        assert "python3.11" in result

    def test_pyenv_versions_sorted_by_version(self, tmp_path: Path) -> None:
        """Pyenv version directories should be yielded in version-sorted order."""
        pyenv_root = tmp_path / "pyenv"
        versions_dir = pyenv_root / "versions"
        versions_dir.mkdir(parents=True)

        for version in ["3.10.5", "3.9.1", "3.12.0", "3.11.3"]:
            ver_dir = versions_dir / version
            (ver_dir / "bin").mkdir(parents=True)
            _make_executable(ver_dir / "bin" / "python")

        # Use an empty PATH bin dir so only pyenv candidates appear
        empty_bin = tmp_path / "empty_bin"
        empty_bin.mkdir()

        with patch.dict("os.environ", {"PYENV": str(pyenv_root)}):
            candidates = [
                c["exact_version"]
                for c in _get_candidates(path_list=[str(empty_bin)], check_pyenv=True)
                if "exact_version" in c and str(versions_dir) in c["path"]
            ]

        assert candidates == ["3.9.1", "3.10.5", "3.11.3", "3.12.0"]
