from kraken.std.docs.tasks.mkdocs import mkdocs

try:
    # HACK: Temporary work around so we can build our docs in CI until Kraken v0.46.0 is released with the
    #       `mkdocs(strict)` parameter. We temporarily build the docs with `kraken` instead of `krakenw` to
    #       use our current version, but should be going back to `krakenw` once that can pick up the right
    #       version of the `mkdocs()` function.
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
        strict=False,
    )
except TypeError:
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