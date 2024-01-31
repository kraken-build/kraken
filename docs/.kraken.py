from kraken.std.docs.tasks.mkdocs import mkdocs

mkdocs(
    requirements=["mkdocs==1.5.3", "pymdown-extensions", "mkdocstrings[python]", "mkdocs-material", "black"],
    watch_files=["../kraken-build/src", "../kraken-wrapper/src"],
)

# novella(
#     novella_version="==0.2.6",
#     additional_requirements=[
#         "mkdocs",
#         "mkdocs-material",
#         "pydoc-markdown==4.8.2",
#         "setuptools",  # Novella/Pydoc-Markdown are using pkg_resources but don't declare setuptools as a dependency
#     ],
#     build_group="build",
#     serve_args=["--serve"],
#     serve_task="serve",
# )
