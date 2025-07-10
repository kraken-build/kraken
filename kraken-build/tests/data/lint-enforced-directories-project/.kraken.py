from kraken.std import python

python.install()
python.python_settings(
    lint_enforced_directories=[
        "./examples",
        "./bin",
    ],
)
python.ruff(version_spec="==0.12.2")
python.mypy(version_spec="==1.8.0")
