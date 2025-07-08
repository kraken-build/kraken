import os

from kraken.std import python

python.python_settings(always_use_managed_env=True).add_package_index(
    alias="local",
    index_url=os.environ["LOCAL_PACKAGE_INDEX"],
    credentials=(os.environ["LOCAL_USER"], os.environ["LOCAL_PASSWORD"]),
)
python.install()
python.mypy(version_spec="==1.10.0")
python.ruff(version_spec="==0.9.4")
python.publish(package_index="local", distributions=python.build(as_version="0.1.0").output_files)
