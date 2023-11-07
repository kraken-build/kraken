import sys
from pathlib import Path


def is_relative_to(apath: Path, bpath: Path) -> bool:
    """
    Checks if *apath* is a path relative to *bpath*.
    """

    if sys.version_info[:2] < (3, 9):
        try:
            apath.relative_to(bpath)
            return True
        except ValueError:
            return False
    else:
        return apath.is_relative_to(bpath)


def try_relative_to(apath: Path, bpath: "Path | None" = None) -> Path:
    """
    Tries to compute the relative path of *apath* relative to *bpath*. Returns the original *apath* if the
    relative path can be be computed, for exmaple if we would need to go at least one directory up to reach
    *apath* relative to *bpath*.
    """

    try:
        return apath.relative_to(bpath or Path.cwd())
    except ValueError:
        return apath
