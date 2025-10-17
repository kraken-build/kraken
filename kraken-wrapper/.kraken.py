from kraken.std import python

python.install()
python.mypy(version_spec="==1.18.2", python_version="3.12")  # mitmproxy latest version requires 3.12
python.ruff(additional_args=["--exclude", "tests/iss-263/example_project"])
python.pytest(
    ignore_dirs=[
        "tests/iss-263/dependency",
        "tests/iss-263/example_project",
    ],
)
