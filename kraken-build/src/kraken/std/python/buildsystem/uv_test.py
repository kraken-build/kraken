from kraken.common.toml import TomlFile
from kraken.std.python.buildsystem.uv import UvIndexes, UvPyprojectHandler
from kraken.std.python.pyproject import PackageIndex, PyprojectHandler
from kraken.std.python.settings import PythonSettings

EXAMPLE_UV_PYPROJECT = """
[project]
name = "uv-project"
version = "0.1.0"
"""


EXAMPLE_UV_PYPROJECT_INDEXES = """
[project]
name = "uv-project"
version = "0.1.0"

[tool.uv]
index-url = "https://example.com/simple/"
extra-index-url = [
    "https://example.org/simple/"
]

[[tool.uv.index]]
name = "foo"
url = "https://example.com/foo/simple/"

[[tool.uv.index]]
name = "bar"
url = "https://example.com/bar/simple/"
explicit = true
"""


EXAMPLE_UV_PYPROJECT_RELATIVE_IMPORT = """
[project]
name = "uv-project"
version = "0.1.0"

dependencies = [
    "tqdm>=4.66.5",
    "uv-project-relative-import",
]

[dependency-groups]
dev = [
    "uv-project-relative-import-dev",
]

[project.optional-dependencies]
opt = [
    "uv-project-relative-import-opt",
]

[tool.uv.sources]
uv-project-relative-import = { path = "../uv-project-relative-import", editable = true }
uv-project-relative-import-dev = { path = "../uv-project-relative-import-dev", editable = true }
uv-project-relative-import-opt = { path = "../uv-project-relative-import-opt", editable = true }
"""


def test__UvIndexes__to_env() -> None:
    indexes = UvIndexes.from_package_indexes(
        [
            PackageIndex(
                alias="foo",
                index_url="https://example.com/foo/simple/",
                priority=PackageIndex.Priority.default,
                verify_ssl=True,
            ),
            PackageIndex(
                alias="bar",
                index_url="https://example.com/bar/simple/",
                priority=PackageIndex.Priority.supplemental,
                verify_ssl=True,
            ),
            PythonSettings._PackageIndex(
                alias="",  # unnamed index
                index_url="https://example.com/simple/",
                priority=PackageIndex.Priority.supplemental,
                verify_ssl=True,
                is_package_source=False,
                publish=True,
                upload_url=None,
                credentials=("usename", "password"),
            ),
        ]
    )
    assert indexes.to_env() == {
        "UV_DEFAULT_INDEX": "https://example.com/foo/simple/",
        "UV_INDEX": "bar=https://example.com/bar/simple/ https://usename:password@example.com/simple/",
    }


def test__UvPyprojectHandler__getters() -> None:
    handler = UvPyprojectHandler(TomlFile.read_string(EXAMPLE_UV_PYPROJECT))
    assert handler.get_name() == "uv-project"
    assert handler.get_version() == "0.1.0"


def test__UvPyprojectHandler__set_version() -> None:
    handler = UvPyprojectHandler(TomlFile.read_string(EXAMPLE_UV_PYPROJECT))
    handler.set_version("2.0.0")
    assert handler.raw["project"]["version"] == "2.0.0"


def test__UvPyprojectHandler__get_package_indexes() -> None:
    handler = UvPyprojectHandler(TomlFile.read_string(EXAMPLE_UV_PYPROJECT_INDEXES))
    assert handler.get_package_indexes() == [
        PackageIndex(
            alias="foo",
            index_url="https://example.com/foo/simple/",
            priority=PackageIndex.Priority.supplemental,
            verify_ssl=True,
        ),
        PackageIndex(
            alias="bar",
            index_url="https://example.com/bar/simple/",
            priority=PackageIndex.Priority.explicit,
            verify_ssl=True,
        ),
        PackageIndex(
            alias="",  # unnamed index
            index_url="https://example.com/simple/",
            priority=PackageIndex.Priority.default,
            verify_ssl=True,
        ),
        PackageIndex(
            alias="",  # unnamed index
            index_url="https://example.org/simple/",
            priority=PackageIndex.Priority.supplemental,
            verify_ssl=True,
        ),
    ]


def test__UvPyprojectHandler__set_package_indexes__to_empty_list() -> None:
    handler = UvPyprojectHandler(TomlFile.read_string(EXAMPLE_UV_PYPROJECT_INDEXES))
    handler.set_package_indexes([])
    assert handler.raw["tool"]["uv"]["index"] == []
    assert not handler.raw["tool"]["uv"].get("index-url")
    assert not handler.raw["tool"]["uv"].get("extra-index-url")


def test__UvPyprojectHandler__set_package_indexes() -> None:
    handler = UvPyprojectHandler(TomlFile.read_string(EXAMPLE_UV_PYPROJECT))
    handler.set_package_indexes(
        [
            PackageIndex("a", "https://example.com/a", PackageIndex.Priority.supplemental, verify_ssl=True),
            PackageIndex("c", "https://example.com/c", PackageIndex.Priority.explicit, verify_ssl=False),
            PackageIndex("b", "https://example.com/b", PackageIndex.Priority.default, verify_ssl=True),
        ]
    )
    assert handler.raw["tool"]["uv"]["index"] == [
        {"name": "b", "url": "https://example.com/b", "default": True},
        {"name": "a", "url": "https://example.com/a"},
        {"name": "c", "url": "https://example.com/c", "explicit": True},
    ]
    assert handler.raw["tool"]["uv"].get("index-url", None) is None
    assert handler.raw["tool"]["uv"].get("extra-index-url", None) is None
    assert handler.raw["tool"]["uv"].get("default-index", None) is None


def test__UvPyprojectHandler__get_packages() -> None:
    handler = UvPyprojectHandler(TomlFile.read_string(EXAMPLE_UV_PYPROJECT))
    assert handler.get_packages() == [PyprojectHandler.Package("uv_project", from_=None)]


def test__UvPyprojectHandler__update_packages() -> None:
    handler = UvPyprojectHandler(TomlFile.read_string(EXAMPLE_UV_PYPROJECT_INDEXES))
    handler.set_package_indexes(handler.get_package_indexes())

    assert "index-url" not in handler.raw["tool"]["uv"]
    assert "extra-index-url" not in handler.raw["tool"]["uv"]
    assert handler.raw["tool"]["uv"]["index"] == [
        {"url": "https://example.com/simple/", "default": True},
        {"url": "https://example.com/foo/simple/", "name": "foo"},
        {"url": "https://example.org/simple/"},
        {"url": "https://example.com/bar/simple/", "name": "bar", "explicit": True},
    ]


def test__UvPyprojectHandler__set_path_dependencies_to_version() -> None:
    handler = UvPyprojectHandler(TomlFile.read_string(EXAMPLE_UV_PYPROJECT_RELATIVE_IMPORT))
    version_to_bump = "0.1.1"
    handler.set_path_dependencies_to_version(version_to_bump)

    assert f"uv-project-relative-import=={version_to_bump}" in handler.raw["project"]["dependencies"]
    assert f"uv-project-relative-import-dev=={version_to_bump}" in handler.raw["dependency-groups"]["dev"]
    assert (
        f"uv-project-relative-import-opt=={version_to_bump}" in handler.raw["project"]["optional-dependencies"]["opt"]
    )
