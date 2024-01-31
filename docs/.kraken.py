from kraken.std.docs.tasks.mkdocs import mkdocs

mkdocs(
    requirements=["mkdocs==1.5.3", "pymdown-extensions", "mkdocstrings[python]", "mkdocs-material", "black"],
    watch_files=["../kraken-build/src", "../kraken-wrapper/src"],
)
