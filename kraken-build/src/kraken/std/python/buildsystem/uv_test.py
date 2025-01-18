from kraken.common.toml import TomlFile
from kraken.std.python.pyproject import PyprojectHandler

from kraken.std.python.buildsystem.uv import UvPyprojectHandler, UvIndexes
from kraken.std.python.pyproject import PackageIndex
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
index-url = "https://abc.com/simple/"
extra-index-url = [
    "https://uvx.com/simple/"
]

[[tool.uv.index]]
name = "foo"
url = "https://foo.com/simple/"

[[tool.uv.index]]
name = "bar"
url = "https://bar.com/simple/"
explicit = true
"""


def test__UvIndexes__to_env() -> None:
    indexes = UvIndexes.from_package_indexes(
        [
            PackageIndex(
                alias="foo",
                index_url="https://foo.com/simple/",
                priority=PackageIndex.Priority.default,
                verify_ssl=True,
            ),
            PackageIndex(
                alias="bar",
                index_url="https://bar.com/simple/",
                priority=PackageIndex.Priority.supplemental,
                verify_ssl=True,
            ),
            PythonSettings._PackageIndex(
                alias="",  # unnamed index
                index_url="https://uvx.com/simple/",
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
        "UV_DEFAULT_INDEX": "https://foo.com/simple/",
        "UV_INDEX": "bar=https://bar.com/simple/ https://usename:password@uvx.com/simple/",
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
            index_url="https://foo.com/simple/",
            priority=PackageIndex.Priority.supplemental,
            verify_ssl=True,
        ),
        PackageIndex(
            alias="bar",
            index_url="https://bar.com/simple/",
            priority=PackageIndex.Priority.explicit,
            verify_ssl=True,
        ),
        PackageIndex(
            alias="",  # unnamed index
            index_url="https://abc.com/simple/",
            priority=PackageIndex.Priority.default,
            verify_ssl=True,
        ),
        PackageIndex(
            alias="",  # unnamed index
            index_url="https://uvx.com/simple/",
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
            PackageIndex("a", "https://a.com", PackageIndex.Priority.supplemental, verify_ssl=True),
            PackageIndex("c", "https://c.com", PackageIndex.Priority.explicit, verify_ssl=False),
            PackageIndex("b", "https://b.com", PackageIndex.Priority.default, verify_ssl=True),
        ]
    )
    assert handler.raw["tool"]["uv"]["index"] == [
        {"name": "a", "url": "https://a.com"},
        {"name": "c", "url": "https://c.com", "explicit": True},
        {"name": "b", "url": "https://b.com", "default": True},
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
        {"url": "https://foo.com/simple/", "name": "foo"},
        {"url": "https://bar.com/simple/", "name": "bar", "explicit": True},
        {"url": "https://abc.com/simple/", "default": True},
        {"url": "https://uvx.com/simple/"},
    ]
