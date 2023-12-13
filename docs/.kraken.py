from kraken.core import Project
from docs_helpers import DocsVenvTask, DocsTask

project = Project.current()

docs_venv = project.task("docsVenv", DocsVenvTask)
docs_venv.directory = project.build_directory / "docs-venev"

docs_build = project.task("docsBuild", DocsTask)
docs_build.venv = docs_venv.directory
docs_build.mode = "build"

docs_serve = project.task("docsServe", DocsTask)
docs_serve.venv = docs_venv.directory
docs_serve.mode = "serve"
