from kraken.std import python

python.pytest(
    ignore_dirs=[
        "tests/iss-263/dependency",
        "tests/iss-263/example_project",
    ],
)
