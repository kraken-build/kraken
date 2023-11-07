from __future__ import annotations

from pathlib import Path

from kraken.core import Project

from kraken.std.cargo import cargo_bump_version, cargo_registry
from kraken.std.cargo.manifest import CargoManifest


def test_cargo_bump_version(kraken_project: Project, tmpdir: Path) -> None:
    cargo_registry(
        "my-registry",
        "https://path-to-some-registry.com",
    )

    cargo_manifest_file = Path(tmpdir) / "Cargo.toml"
    with cargo_manifest_file.open("w") as f:
        f.write(
            """[package]
name = "awesome-package"
version.workspace = true
edition.workspace = true
authors.workspace = true
documentation.workspace = true

[[bin]]
name = "awesome"
path = "src/main.rs"

[dependencies]
reqwest = { version = "^0.11.16", features = ["json", "blocking"] }
awesome-dependency = { path = "../awesome" }

[build-dependencies]
awesome-build-dependency = { path = "../awesome-build" }
"""
        )

    task = cargo_bump_version(
        version="1.1.0",
        project=kraken_project,
        registry="my-registry",
        revert=False,
        cargo_toml_file=cargo_manifest_file,
    )
    task_status = task.execute()
    assert task_status is not None
    assert task_status.is_succeeded()
    cargo_manifest = CargoManifest.read(cargo_manifest_file)
    assert cargo_manifest.dependencies is not None
    assert cargo_manifest.dependencies.data == {
        "awesome-dependency": {"path": "../awesome", "registry": "my-registry", "version": "=1.1.0"},
        "reqwest": {"features": ["json", "blocking"], "version": "^0.11.16"},
    }
    assert cargo_manifest.build_dependencies is not None
    assert cargo_manifest.build_dependencies.data == {
        "awesome-build-dependency": {"path": "../awesome-build", "registry": "my-registry", "version": "=1.1.0"},
    }
