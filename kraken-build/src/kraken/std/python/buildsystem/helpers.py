"""Python build system helper functions"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path


def update_python_version_str_in_source_files(as_version: str, package_directory: Path) -> Iterable[tuple[Path, int]]:
    """
    Updates the `__version__` in Python source files in the given *package_directory*. The constant is commonly
    contained in the files `__init__.py`, `__about__.py` and `_version.py`. No such files in subdirectories will
    be updated. The *package_directory* is expected to point at the directory that contains directly the file(s)
    with the `__version__` constant.

    Yields the paths that are _about to_ being updated and the number of occurrences per file.
    """

    FILENAMES = ["__init__.py", "__about__.py", "_version.py"]
    VERSION_REGEX = r'__version__\s*=\s*[\'"]([^\'"]+)[\'"]'
    replace_with = f'__version__ = "{as_version}"'
    sum_replaced = 0

    for source_file_path in package_directory.glob("*.py"):
        if source_file_path.name not in FILENAMES:
            continue
        source_file_path_ = Path(source_file_path)
        content = source_file_path_.read_text()
        (content, n_replaced) = re.subn(VERSION_REGEX, replace_with, content, flags=re.M)
        if n_replaced > 0:
            yield source_file_path, n_replaced
            source_file_path_.write_text(content)
        sum_replaced += n_replaced
