import pytest

from kraken.core.system.project import Project
from kraken.core.system.task import VoidTask


def test__Project__do_normalizes_taskname_backwards_compatibility_pre_0_12_0(kraken_project: Project) -> None:
    with pytest.warns(DeprecationWarning) as warninfo:
        task = kraken_project.task("this is a :test task", VoidTask)
    assert task.name == "this-is-a-test-task"
    assert str(warninfo.list[0].message) == ("Call to deprecated method do. (Use Project.task() instead)")
    assert str(warninfo.list[1].message) == (
        "Task name `this is a :test task` is invalid and will be normalized to `this-is-a-test-task`. "
        "Starting with kraken-core 0.12.0, Task names must follow a stricter naming convention subject to the "
        "Address class' validation (must match /^[a-zA-Z0-9/_\\-\\.\\*]+$/)."
    )
