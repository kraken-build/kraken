import os

from kraken.std import python

python.python_settings(always_use_managed_env=True).add_package_index(
    alias="local",
    index_url=os.environ["LOCAL_PACKAGE_INDEX"],
    credentials=(os.environ["LOCAL_USER"], os.environ["LOCAL_PASSWORD"]),
)
python.install()
python.mypy()
python.flake8()
python.black()
python.isort()
python.pytest()
python.publish(package_index="local", distributions=python.build(as_version="0.1.0").output_files)
