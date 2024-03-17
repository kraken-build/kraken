import os

from kraken.std.python.project import python_package_index, python_project

python_package_index(
    alias="local",
    index_url=os.environ["LOCAL_PACKAGE_INDEX"],
    credentials=(os.environ["LOCAL_USER"], os.environ["LOCAL_PASSWORD"]),
    publish=True,
)
python_project()
