import dataclasses
from enum import Enum


@dataclasses.dataclass
class IndexPriority(str, Enum):
    """See https://python-poetry.org/docs/repositories/#project-configuration"""

    default = "default"
    primary = "primary"
    secondary = "secondary"
    supplemental = "supplemental"


@dataclasses.dataclass
class PythonIndex:
    alias: str
    index_url: str
    upload_url: str | None
    credentials: tuple[str, str] | None
    is_package_source: bool
    priority: IndexPriority
    publish: bool
