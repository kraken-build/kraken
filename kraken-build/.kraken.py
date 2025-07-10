from kraken.std import python

python.install()
python.mypy(version_spec="==1.16.1")
python.ruff(additional_args=["--exclude", "tests/data"])
python.pytest(
    tests_dir=["src", "tests/kraken_core"],
    include_dirs=["src/kraken/build"],
)
python.pytest(
    name="pytest-e2e",
    tests_dir=["tests/kraken_std"],
    ignore_dirs=["tests/kraken_std/data"],
)
