import os

from kraken.std import python_package_index, python_project
from kraken.std.python import mypy_stubtest

python_package_index(
    alias="local",
    index_url=os.environ["LOCAL_PACKAGE_INDEX"],
    credentials=(os.environ["LOCAL_USER"], os.environ["LOCAL_PASSWORD"]),
    publish=True,
)
python_project(enforce_project_version="0.1.0")

mypy_stubtest(package="rust_pdm_project", ignore_missing_stubs=True)
