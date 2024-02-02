import os

from kraken.std.python.project import python_library, python_package_index

python_package_index(
    alias="local",
    index_url=os.environ["LOCAL_PACKAGE_INDEX"],
    is_package_source=False,
    credentials=(os.environ["LOCAL_USER"], os.environ["LOCAL_PASSWORD"]),
)

python_library()

# python.python_settings(always_use_managed_env=True).add_package_index(
# )
# python.install()
# python.mypy()
# python.publish(package_index="local", distributions=python.build(as_version="0.1.0").output_files)
