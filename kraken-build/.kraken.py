from kraken.std import python

python.install()
python.mypy(version_spec="==1.18.2", python_version="3.12")  # mitmproxy latest version requires 3.12
python.ruff(additional_args=["--exclude", "tests/data"])
python.pytest(
    tests_dir=["src", "tests/kraken_core"],
)
python.pytest(
    name="pytest-e2e",
    tests_dir=["tests/kraken_std"],
    ignore_dirs=["tests/kraken_std/data"],
)
