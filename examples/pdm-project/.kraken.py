import os

from kraken.std.python.project import python_project, python_package_index

python_package_index(
    alias="local",
    index_url=os.environ["LOCAL_PACKAGE_INDEX"],
    is_package_source=False,
    publish=True,
    credentials=(os.environ["LOCAL_USER"], os.environ["LOCAL_PASSWORD"]),
)

python_project()
