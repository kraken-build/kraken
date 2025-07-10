from kraken.std import python

python.install()
python.mypy(version_spec="==1.16.1")
python.ruff(additional_args=["--exclude", "tests/iss-263/example_project"])
python.pytest(
    ignore_dirs=[
        "tests/iss-263/dependency",
        "tests/iss-263/example_project",
    ],
)
