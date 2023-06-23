from kraken.std.python.buildsystem.pdm import PdmPyprojectHandler
from kraken.std.python.pyproject import PackageIndex, Pyproject

EXAMPLE_PDM_PYPROJECT = """
[project]
name = "pdm-project"
version = "0.1.0"

[[tool.pdm.source]]
name = "private"
url = "https://private.pypi.org/simple"
verify_ssl = true
"""


def test__PdmPyprojectHandler__getters() -> None:
    handler = PdmPyprojectHandler(Pyproject.read_string(EXAMPLE_PDM_PYPROJECT))
    assert handler.get_name() == "pdm-project"
    assert handler.get_version() == "0.1.0"


def test__PdmPyprojectHandler__set_version() -> None:
    handler = PdmPyprojectHandler(Pyproject.read_string(EXAMPLE_PDM_PYPROJECT))
    handler.set_version("2.0.0")
    assert handler.raw["project"]["version"] == "2.0.0"


def test__PdmPyprojectHandler__get_package_indexes() -> None:
    handler = PdmPyprojectHandler(Pyproject.read_string(EXAMPLE_PDM_PYPROJECT))
    assert handler.get_package_indexes() == [
        PackageIndex(
            alias="private",
            index_url="https://private.pypi.org/simple",
            priority=PackageIndex.Priority.primary,
            verify_ssl=True,
        )
    ]


def test__PdmPyprojectHandler__set_package_indexes__to_empty_list() -> None:
    handler = PdmPyprojectHandler(Pyproject.read_string(EXAMPLE_PDM_PYPROJECT))
    handler.set_package_indexes([])
    assert handler.raw["tool"]["pdm"]["source"] == []


def test__PdmPyprojectHandler__set_package_indexes__to_various_indexes() -> None:
    handler = PdmPyprojectHandler(Pyproject.read_string(EXAMPLE_PDM_PYPROJECT))
    handler.set_package_indexes(
        [
            PackageIndex("a", "https://a.com", PackageIndex.Priority.primary, True),
            PackageIndex("c", "https://c.com", PackageIndex.Priority.supplemental, False),
            PackageIndex("b", "https://b.com", PackageIndex.Priority.default, True),
        ]
    )
    assert handler.raw["tool"]["pdm"]["source"] == [
        {"name": "b", "url": "https://b.com"},
        {"name": "a", "url": "https://a.com"},
        {"name": "c", "url": "https://c.com", "verify_ssl": False},
    ]
