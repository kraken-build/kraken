from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from kraken.core import Context, Project
from kraken.std.cargo import CargoHackFeatures, cargo_hack

DATA_PATH = Path(__file__).parent / "data"
CARGO_PROJECT_CORRECT_FEATURES_PATH = DATA_PATH / "correct_features"
CARGO_PROJECT_INCORRECT_FEATURES_PATH = DATA_PATH / "incorrect_features"
CARGO_PROJECT_INCORRECT_MULTI_FEATURES_PATH = DATA_PATH / "incorrect_multi_features"


def test__cargo_hack__succeeds_correct_features() -> None:
    with TemporaryDirectory() as t:
        output_path = Path(t)
        create_cargo_project(CARGO_PROJECT_CORRECT_FEATURES_PATH, output_path)

        task = cargo_hack(
            project=Project(
                name="test_project", directory=output_path, context=Context(build_directory=output_path), parent=None
            ),
        )
        assert task.execute().is_succeeded()


def test__cargo_hack__fails_incorrect_features() -> None:
    with TemporaryDirectory() as t:
        output_path = Path(t)
        create_cargo_project(CARGO_PROJECT_INCORRECT_FEATURES_PATH, output_path)

        task = cargo_hack(
            project=Project(
                name="test_project", directory=output_path, context=Context(build_directory=output_path), parent=None
            ),
        )
        assert task.execute().is_failed()


def test__cargo_hack__succeeds_incorrect_multi_features() -> None:
    with TemporaryDirectory() as t:
        output_path = Path(t)
        create_cargo_project(CARGO_PROJECT_INCORRECT_MULTI_FEATURES_PATH, output_path)

        task = cargo_hack(
            project=Project(
                name="test_project", directory=output_path, context=Context(build_directory=output_path), parent=None
            ),
        )
        assert task.execute().is_succeeded()


def test__cargo_hack__fails_incorrect_multi_features() -> None:
    with TemporaryDirectory() as t:
        output_path = Path(t)
        create_cargo_project(CARGO_PROJECT_INCORRECT_MULTI_FEATURES_PATH, output_path)

        task = cargo_hack(
            project=Project(
                name="test_project", directory=output_path, context=Context(build_directory=output_path), parent=None
            ),
            features=CargoHackFeatures.POWERSET,
        )
        assert task.execute().is_failed()


def create_cargo_project(project: Path, target: Path) -> None:
    shutil.copytree(project / "src", target / "src")
    shutil.copy(project / "Cargo.toml", target)
    shutil.copy(project / "Cargo.lock", target)
