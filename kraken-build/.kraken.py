from kraken.std import python

python.pytest(
    tests_dir=["src", "tests/kraken_core"],
    include_dirs=["src/kraken/build"],
)
python.pytest(
    name="pytest-e2e",
    tests_dir=["tests/kraken_std"],
    ignore_dirs=["tests/kraken_std/data"],
)
