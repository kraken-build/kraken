from kraken.std.python.buildsystem.poetry import PoetryPyprojectHandler
from kraken.std.python.pyproject import PackageIndex, Pyproject

EXAMPLE_POETRY_PYPROJECT = """
[tool.poetry]
name = "poetry-project"
version = "0.1.0"

[[tool.poetry.source]]
name = "foo"
url = "https://foo.bar/simple/"
priority = "supplemental"
"""

EXAMPLE_POETRY_PYPROJECT_WITH_LEGACY_SOURCE_CONFIG = """
[[tool.poetry.source]]
name = "foo"
url = "https://foo.bar/simple/"
default = true

[[tool.poetry.source]]
name = "bar"
url = "https://bar.com/simple/"
secondary = true
"""


def test__PoetryPyprojectHandler__getters() -> None:
    handler = PoetryPyprojectHandler(Pyproject.read_string(EXAMPLE_POETRY_PYPROJECT))
    assert handler.get_name() == "poetry-project"
    assert handler.get_version() == "0.1.0"


def test__PoetryPyprojectHandler__set_version() -> None:
    handler = PoetryPyprojectHandler(Pyproject.read_string(EXAMPLE_POETRY_PYPROJECT))
    handler.set_version("2.0.0")
    assert handler.raw["tool"]["poetry"]["version"] == "2.0.0"


def test__PoetryPyprojectHandler__get_package_indexes() -> None:
    handler = PoetryPyprojectHandler(Pyproject.read_string(EXAMPLE_POETRY_PYPROJECT))
    assert handler.get_package_indexes() == [
        PackageIndex(
            alias="foo",
            index_url="https://foo.bar/simple/",
            priority=PackageIndex.Priority.supplemental,
            verify_ssl=True,
        )
    ]


def test__PoetryPyprojectHandler__get_package_indexes__with_legacy_source_config() -> None:
    handler = PoetryPyprojectHandler(Pyproject.read_string(EXAMPLE_POETRY_PYPROJECT_WITH_LEGACY_SOURCE_CONFIG))
    assert handler.get_package_indexes() == [
        PackageIndex(
            alias="foo",
            index_url="https://foo.bar/simple/",
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
    handler = PoetryPyprojectHandler(Pyproject.read_string(EXAMPLE_POETRY_PYPROJECT))
    handler.set_package_indexes([])
    assert handler.raw["tool"]["poetry"]["source"] == []


def test__PoetryPyprojectHandler__set_package_indexes__to_various_indexes() -> None:
    handler = PoetryPyprojectHandler(Pyproject.read_string(EXAMPLE_POETRY_PYPROJECT))
    handler.set_package_indexes(
        [
            PackageIndex("a", "https://a.com", PackageIndex.Priority.primary, True),
            PackageIndex("c", "https://c.com", PackageIndex.Priority.supplemental, False),
            PackageIndex("b", "https://b.com", PackageIndex.Priority.default, True),
        ]
    )
    assert handler.raw["tool"]["poetry"]["source"] == [
        {"name": "a", "url": "https://a.com", "priority": "primary"},
        {"name": "c", "url": "https://c.com", "priority": "supplemental"},
        {"name": "b", "url": "https://b.com", "priority": "default"},
    ]
