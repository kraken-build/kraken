from pathlib import Path

from kraken.std.cargo.manifest import CargoMetadata


def test_cargo_metadata_parses_correctly() -> None:
    metadata = CargoMetadata.of(
        Path(""),
        {
            "packages": [
                {
                    "name": "some-bin",
                    "version": "0.1.0",
                    "id": "some-bin 0.1.0 (path+file:///Users/ow/src/clarity/cargo-workspace/some-bin)",
                    "license": None,
                    "license_file": None,
                    "description": None,
                    "source": None,
                    "dependencies": [],
                    "targets": [
                        {
                            "kind": ["bin"],
                            "crate_types": ["bin"],
                            "name": "some-bin",
                            "src_path": "/Users/ow/src/clarity/cargo-workspace/some-bin/src/main.rs",
                            "edition": "2021",
                            "doc": True,
                            "doctest": False,
                            "test": True,
                        },
                        {
                            "kind": ["bin"],
                            "crate_types": ["bin"],
                            "name": "second",
                            "src_path": "/Users/ow/src/clarity/cargo-workspace/some-bin/src/bin/second.rs",
                            "edition": "2021",
                            "doc": True,
                            "doctest": False,
                            "test": True,
                        },
                        {
                            "kind": ["bin"],
                            "crate_types": ["bin"],
                            "name": "first",
                            "src_path": "/Users/ow/src/clarity/cargo-workspace/some-bin/src/bin/first.rs",
                            "edition": "2021",
                            "doc": True,
                            "doctest": False,
                            "test": True,
                        },
                    ],
                    "features": {},
                    "manifest_path": "/Users/ow/src/clarity/cargo-workspace/some-bin/Cargo.toml",
                    "metadata": None,
                    "publish": None,
                    "authors": [],
                    "categories": [],
                    "keywords": [],
                    "readme": None,
                    "repository": None,
                    "homepage": None,
                    "documentation": None,
                    "edition": "2021",
                    "links": None,
                    "default_run": None,
                    "rust_version": None,
                },
                {
                    "name": "some-lib",
                    "version": "0.1.0",
                    "id": "some-lib 0.1.0 (path+file:///Users/ow/src/clarity/cargo-workspace/some-lib)",
                    "license": None,
                    "license_file": None,
                    "description": None,
                    "source": None,
                    "dependencies": [],
                    "targets": [
                        {
                            "kind": ["lib"],
                            "crate_types": ["lib"],
                            "name": "some-lib",
                            "src_path": "/Users/ow/src/clarity/cargo-workspace/some-lib/src/lib.rs",
                            "edition": "2021",
                            "doc": True,
                            "doctest": True,
                            "test": True,
                        },
                        {
                            "kind": ["bin"],
                            "crate_types": ["bin"],
                            "name": "some-lib-also-has-bin",
                            "src_path": "/Users/ow/src/clarity/cargo-workspace/some-lib/src/bin/some-lib-also-has-bin.rs",  # noqa: E501
                            "edition": "2021",
                            "doc": True,
                            "doctest": False,
                            "test": True,
                        },
                    ],
                    "features": {},
                    "manifest_path": "/Users/ow/src/clarity/cargo-workspace/some-lib/Cargo.toml",
                    "metadata": None,
                    "publish": None,
                    "authors": [],
                    "categories": [],
                    "keywords": [],
                    "readme": None,
                    "repository": None,
                    "homepage": None,
                    "documentation": None,
                    "edition": "2021",
                    "links": None,
                    "default_run": None,
                    "rust_version": None,
                },
            ],
            "workspace_members": [
                "some-lib 0.1.0 (path+file:///Users/ow/src/clarity/cargo-workspace/some-lib)",
                "some-bin 0.1.0 (path+file:///Users/ow/src/clarity/cargo-workspace/some-bin)",
            ],
            "resolve": {
                "nodes": [
                    {
                        "id": "some-bin 0.1.0 (path+file:///Users/ow/src/clarity/cargo-workspace/some-bin)",
                        "dependencies": [],
                        "deps": [],
                        "features": [],
                    },
                    {
                        "id": "some-lib 0.1.0 (path+file:///Users/ow/src/clarity/cargo-workspace/some-lib)",
                        "dependencies": [],
                        "deps": [],
                        "features": [],
                    },
                ],
                "root": None,
            },
            "target_directory": "/Users/ow/src/clarity/cargo-workspace/target",
            "version": 1,
            "workspace_root": "/Users/ow/src/clarity/cargo-workspace",
            "metadata": None,
        },
    )

    members = list(map(lambda x: x.name, metadata.workspaceMembers))
    members.sort()
    assert members == ["some-bin", "some-lib"]
    assert len(metadata.artifacts) == 5
