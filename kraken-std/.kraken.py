from __future__ import annotations

from kraken.common import buildscript

buildscript(requirements=["kraken-std@."])

import os

from kraken.core.api import Project

from kraken.std import python
from kraken.std.git import git_describe

project = Project.current()
python.pyupgrade(additional_files=[__file__, project.directory / "examples"], keep_runtime_typing=True)
python.pycln()
python.black(additional_files=[__file__, project.directory / "examples"])
python.flake8()
python.isort(additional_files=[__file__, project.directory / "examples"])
python.mypy(additional_args=["--exclude", "src/tests/integration/.*/data/.*"])
python.pytest(ignore_dirs=["src/tests/integration"])
python.pytest(
    name="pytestIntegration",
    tests_dir="src/tests/integration",
    ignore_dirs=["src/tests/integration/python/data"],
    group="integrationTest",
)
python.install()

(
    python.python_settings()
    .add_package_index(
        "pypi",
        credentials=(os.environ["PYPI_USER"], os.environ["PYPI_PASSWORD"]) if "PYPI_USER" in os.environ else None,
    )
    .add_package_index(
        "testpypi",
        credentials=(os.environ["TESTPYPI_USER"], os.environ["TESTPYPI_PASSWORD"])
        if "TESTPYPI_USER" in os.environ
        else None,
    )
)

do_publish = True
as_version: str | None = None
if "CI" in os.environ:
    if os.environ["GITHUB_REF_TYPE"] == "tag":
        # TODO (@NiklasRosenstein): It would be nice to add a test that checks if the version in the package
        #       is consistent (ie. run `slap release --validate <tag>`).
        is_release = True
        as_version = os.environ["GITHUB_REF_NAME"]
    elif os.environ["GITHUB_REF_TYPE"] == "branch":
        if os.environ["GITHUB_REF_NAME"] == "develop":
            is_release = False
            as_version = python.git_version_to_python(git_describe(project.directory), include_sha=False)
        else:
            # NOTE (@NiklasRosenstein): PyPI/TestPypi cannot use PEP 440 local versions (which the version with
            #       included SHA would qualify as), so we don't publish from branches at all.
            do_publish = False
    else:
        raise EnvironmentError(
            f"GITHUB_REF_TYPE={os.environ['GITHUB_REF_TYPE']}, GITHUB_REF_NAME={os.environ['GITHUB_REF_NAME']}"
        )
else:
    do_publish = False
    is_release = False
    as_version = python.git_version_to_python(git_describe(project.directory), include_sha=False)


build_task = python.build(as_version=as_version)

if do_publish:
    testpypi = python.publish(
        name="publishToTestPypi",
        package_index="testpypi",
        distributions=build_task.output_files,
        skip_existing=True,
    )
    if is_release:
        python.publish(
            name="publishToPypi",
            package_index="pypi",
            distributions=build_task.output_files,
            after=[testpypi],
        )
