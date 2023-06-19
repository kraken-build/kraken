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
python.pytest(numprocesses="auto")
python.publish(package_index="local", distributions=python.build().output_files)
