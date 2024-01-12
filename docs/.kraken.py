from kraken.std.docs.tasks.novella import novella

novella(
    novella_version="==0.2.6",
    additional_requirements=[
        "mkdocs",
        "mkdocs-material",
        "pydoc-markdown==4.8.2",
        "setuptools",  # Novella/Pydoc-Markdown are using pkg_resources but don't declare setuptools as a dependency
    ],
    build_group="build",
    serve_args=["--serve"],
    serve_task="serve",
)
