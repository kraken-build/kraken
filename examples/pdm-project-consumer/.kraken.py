import os

from kraken.build.python.v1alpha1 import python_package_index, python_project

python_package_index(
    alias="local",
    index_url=os.environ["LOCAL_PACKAGE_INDEX"],
    credentials=(os.environ["LOCAL_USER"], os.environ["LOCAL_PASSWORD"]),
)
python_project(enforce_project_version="0.1.0")
