from kraken.common.toml import TomlFile
from kraken.std.python.pyproject import PyprojectHandler

from kraken.std.python.buildsystem.poetry import PoetryPyprojectHandler
from kraken.std.python.pyproject import PackageIndex

EXAMPLE_POETRY_PYPROJECT = """
[tool.poetry]
name = "poetry-project"
version = "0.1.0"

[[tool.poetry.source]]
name = "foo"
url = "https://foo.com/simple/"
priority = "supplemental"
"""

EXAMPLE_POETRY_PYPROJECT_WITH_LEGACY_SOURCE_CONFIG = """
[[tool.poetry.source]]
name = "foo"
url = "https://foo.com/simple/"
default = true

[[tool.poetry.source]]
name = "bar"
url = "https://bar.com/simple/"
secondary = true
"""

EXAMPLE_POETRY_PYPROJECT_INCLUDED_PACKAGES = """
[tool.poetry]
name = "poetry-project"
version = "0.1.0"
packages = [
  {include = "kraken/build", from = "src"},
  {include = "kraken/common", from = "src"},
  {include = "kraken/core", from = "src"},
  {include = "kraken/std", from = "src"},
]
"""


def test__PoetryPyprojectHandler__getters() -> None:
    handler = PoetryPyprojectHandler(TomlFile.read_string(EXAMPLE_POETRY_PYPROJECT))
    assert handler.get_name() == "poetry-project"
    assert handler.get_version() == "0.1.0"


def test__PoetryPyprojectHandler__set_version() -> None:
    handler = PoetryPyprojectHandler(TomlFile.read_string(EXAMPLE_POETRY_PYPROJECT))
    handler.set_version("2.0.0")
    assert handler.raw["tool"]["poetry"]["version"] == "2.0.0"


def test__PoetryPyprojectHandler__get_package_indexes() -> None:
    handler = PoetryPyprojectHandler(TomlFile.read_string(EXAMPLE_POETRY_PYPROJECT))
    assert handler.get_package_indexes() == [
        PackageIndex(
            alias="foo",
            index_url="https://foo.com/simple/",
            priority=PackageIndex.Priority.supplemental,
            verify_ssl=True,
        )
    ]


def test__PoetryPyprojectHandler__get_package_indexes__with_legacy_source_config() -> None:
    handler = PoetryPyprojectHandler(TomlFile.read_string(EXAMPLE_POETRY_PYPROJECT_WITH_LEGACY_SOURCE_CONFIG))
    assert handler.get_package_indexes() == [
        PackageIndex(
            alias="foo",
            index_url="https://foo.com/simple/",
            priority=PackageIndex.Priority.default,
            verify_ssl=True,
        ),
        PackageIndex(
            alias="bar",
            index_url="https://bar.com/simple/",
            priority=PackageIndex.Priority.secondary,
            verify_ssl=True,
        ),
    ]


def test__PoetryPyprojectHandler__set_package_indexes__to_empty_list() -> None:
    handler = PoetryPyprojectHandler(TomlFile.read_string(EXAMPLE_POETRY_PYPROJECT))
    handler.set_package_indexes([])
    assert handler.raw["tool"]["poetry"]["source"] == []


def test__PoetryPyprojectHandler__set_package_indexes__to_various_indexes() -> None:
    handler = PoetryPyprojectHandler(TomlFile.read_string(EXAMPLE_POETRY_PYPROJECT))
    handler.set_package_indexes(
        [
            PackageIndex("a", "https://a.com", PackageIndex.Priority.primary, verify_ssl=True),
            PackageIndex("c", "https://c.com", PackageIndex.Priority.supplemental, verify_ssl=False),
            PackageIndex("b", "https://b.com", PackageIndex.Priority.default, verify_ssl=True),
        ]
    )
    assert handler.raw["tool"]["poetry"]["source"] == [
        {"name": "a", "url": "https://a.com", "priority": "primary"},
        {"name": "c", "url": "https://c.com", "priority": "supplemental"},
        {"name": "b", "url": "https://b.com", "priority": "default"},
    ]


def test__PoetryPyprojectHandler__get_packages_without_includes() -> None:
    handler = PoetryPyprojectHandler(TomlFile.read_string(EXAMPLE_POETRY_PYPROJECT))
    assert handler.get_packages() == [PyprojectHandler.Package("poetry_project", from_=None)]


def test__PoetryPyprojectHandler__get_packages_with_includes() -> None:
    handler = PoetryPyprojectHandler(TomlFile.read_string(EXAMPLE_POETRY_PYPROJECT_INCLUDED_PACKAGES))
    assert handler.get_packages() == [
        PyprojectHandler.Package("kraken/build", from_="src"),
        PyprojectHandler.Package("kraken/common", from_="src"),
        PyprojectHandler.Package("kraken/core", from_="src"),
        PyprojectHandler.Package("kraken/std", from_="src"),
    ]
