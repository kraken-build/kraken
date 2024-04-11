from dataclasses import dataclass

import pytest

from kraken.core.system.project import Project
from kraken.core.system.property import Property
from kraken.core.system.task import Task, VoidTask


@dataclass
class MyDescriptor:
    name: str


def test__Project__resolve_outputs__can_find_dataclass_in_metadata(kraken_project: Project) -> None:
    kraken_project.task("carrier", VoidTask).outputs.append(MyDescriptor("foobar"))
    assert list(kraken_project.resolve_tasks(":carrier").select(MyDescriptor).all()) == [MyDescriptor("foobar")]


def test__Project__resolve_outputs__can_find_dataclass_in_properties(kraken_project: Project) -> None:
    class MyTask(Task):
        out_prop: Property[MyDescriptor] = Property.output()

        def execute(self) -> None:
            ...

    task = kraken_project.task("carrier", MyTask)
    task.out_prop = MyDescriptor("foobar")
    assert list(kraken_project.resolve_tasks(":carrier").select(MyDescriptor).all()) == [MyDescriptor("foobar")]


def test__Project__resolve_outputs__can_not_find_input_property(kraken_project: Project) -> None:
    class MyTask(Task):
        out_prop: Property[MyDescriptor]

        def execute(self) -> None:
            ...

    task = kraken_project.task("carrier", MyTask)
    task.out_prop = MyDescriptor("foobar")
    assert list(kraken_project.resolve_tasks(":carrier").select(MyDescriptor).all()) == []


def test__Project__resolve_outputs_supplier(kraken_project: Project) -> None:
    class MyTask(Task):
        out_prop: Property[MyDescriptor] = Property.output()

        def execute(self) -> None:
            ...

    task = kraken_project.task("carrier", MyTask)
    task.out_prop = MyDescriptor("foobar")
    assert kraken_project.resolve_tasks(":carrier").select(MyDescriptor).supplier().get() == [MyDescriptor("foobar")]


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


def test__Project__do__does_not_set_property_on_None_value(kraken_project: Project) -> None:
    class MyTask(Task):
        in_prop: Property[str]

        def execute(self) -> None:
            ...

    kraken_project.task("carrier", MyTask)
    assert kraken_project.resolve_tasks(":carrier").select(str).supplier().get() == []
