
import os
from pathlib import Path
import subprocess as sp
from mkdocs.structure.pages import Page
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.files import Files
from mksync import mksync_file


def on_page_read_source(page: Page, config: MkDocsConfig) -> str:
    path = Path(page.file.abs_src_path)
    cwd = os.getcwd()
    os.chdir(path.parent)
    try:
        result = mksync_file(path)
    finally:
        os.chdir(cwd)
    return result.content
