from dataclasses import dataclass

from pytest import raises

from kraken.core.system.project import Project
from kraken.core.system.property import Property
from kraken.core.system.task import Task, TaskRelationship, TaskSet, VoidTask


def test__Task__get_relationships_lineage_through_properties(kraken_project: Project) -> None:
    class MyTask(Task):
        prop: Property[str]

        def execute(self) -> None:
            raise NotImplementedError

    t1 = kraken_project.task("t1", MyTask)
    t1.prop.set("Hello, World")

    t2 = kraken_project.task("t2", MyTask)
    t2.prop.set(t1.prop)

    assert list(t2.get_relationships()) == [TaskRelationship(t1, True, False)]


def test__Task__new_style_type_hints_can_be_runtime_introspected_in_all_Python_versions(
    kraken_project: Project,
) -> None:
    """This is a feature of `typeapi ^1.3.0`."""

    class MyTask(Task):
        a: Property["list[str]"]
        b: Property["int | str"]

        def execute(self) -> None:
            raise NotImplementedError

    t1 = kraken_project.task("t1", MyTask)
    t1.a.set(["a", "b"])
    t1.b.set(42)
    t1.b.set("foo")

    with raises(TypeError) as excinfo:
        t1.a.set(("a", "b"))  # type: ignore[arg-type]
    assert str(excinfo.value) == "Property(MyTask(:t1).a): expected list, got tuple"
    with raises(TypeError) as excinfo:
        t1.b.set(42.0)  # type: ignore[arg-type]
    assert str(excinfo.value) == "Property(MyTask(:t1).b): expected int, got float\nexpected str, got float"


@dataclass
class MyDescriptor:
    name: str


def test__TaskSet__resolve_outputs__can_find_dataclass_in_metadata(kraken_project: Project) -> None:
    kraken_project.task("carrier", VoidTask).outputs.append(MyDescriptor("foobar"))
    assert list(TaskSet.build(kraken_project, ":carrier").select(MyDescriptor).all()) == [MyDescriptor("foobar")]


def test__TaskSet__resolve_outputs__can_find_dataclass_in_properties(kraken_project: Project) -> None:
    class MyTask(Task):
        out_prop: Property[MyDescriptor] = Property.output()

        def execute(self) -> None: ...

    task = kraken_project.task("carrier", MyTask)
    task.out_prop = MyDescriptor("foobar")
    assert list(TaskSet.build(kraken_project, ":carrier").select(MyDescriptor).all()) == [MyDescriptor("foobar")]


def test__TaskSet__resolve_outputs__can_not_find_input_property(kraken_project: Project) -> None:
    class MyTask(Task):
        out_prop: Property[MyDescriptor]

        def execute(self) -> None: ...

    task = kraken_project.task("carrier", MyTask)
    task.out_prop = MyDescriptor("foobar")
    assert list(TaskSet.build(kraken_project, ":carrier").select(MyDescriptor).all()) == []


def test__TaskSet__resolve_outputs_supplier(kraken_project: Project) -> None:
    class MyTask(Task):
        out_prop: Property[MyDescriptor] = Property.output()

        def execute(self) -> None: ...

    task = kraken_project.task("carrier", MyTask)
    task.out_prop = MyDescriptor("foobar")
    assert TaskSet.build(kraken_project, ":carrier").select(MyDescriptor).supplier().get() == [MyDescriptor("foobar")]


def test__TaskSet__do__does_not_set_property_on_None_value(kraken_project: Project) -> None:
    class MyTask(Task):
        in_prop: Property[str]

        def execute(self) -> None: ...

    kraken_project.task("carrier", MyTask)
    assert TaskSet.build(kraken_project, ":carrier").select(str).supplier().get() == []
