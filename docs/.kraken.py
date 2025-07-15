from kraken.std.docs.tasks.mkdocs import mkdocs

mkdocs(
    requirements=[
        "mkdocs==1.6.1",
        "pymdown-extensions",
        "mkdocstrings[python]==0.29.1",
        "mkdocstrings-python==1.16.12",
        "mkdocstrings-python-xref==1.16.3",
        "mkdocs-material",
        "black",
        "mksync",
    ],
    watch_files=["../kraken-build/src", "../kraken-wrapper/src"],
)
