from kraken.std import python

python.pytest(ignore_dirs=["src/tests/integration"], include_dirs=["src/kraken/build"])
