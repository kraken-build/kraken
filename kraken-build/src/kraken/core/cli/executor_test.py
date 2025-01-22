import termcolor

from kraken.core.cli.executor import COLORS_BY_STATUS
from kraken.core.system.task import TaskStatusType


def test__COLORS_BY_STATUS__contains_a_color_for_every_status() -> None:
    for key in TaskStatusType:
        assert key in COLORS_BY_STATUS
        assert COLORS_BY_STATUS[key] in termcolor.COLORS
