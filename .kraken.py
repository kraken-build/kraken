from kraken.common import buildscript

buildscript(requirements=["kraken-build>=0.44.0"])

from kraken.build import project  # noqa: E402
from kraken.std import python  # noqa: E402
from kraken.std.git import gitignore  # noqa: E402


def configure_project() -> None:
    python.install()
    python.ruff(additional_args=["--exclude", "tests/iss-263/example_project"])
    python.mypy(version_spec="==1.16.1")


gitignore()
project.subproject("docs")
for subproject in [
    project.subproject("kraken-build"),
    project.subproject("kraken-wrapper"),
]:
    with subproject.as_current():
        configure_project()
