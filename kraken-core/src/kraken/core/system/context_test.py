from pathlib import Path

from pytest import raises

from kraken.core.address import AddressResolutionError
from kraken.core.system.context import TaskResolutionException
from kraken.core.system.project import Project
from kraken.core.system.task import VoidTask


def test__Context__resolve_tasks(kraken_project: Project) -> None:
    context = kraken_project.context

    # Generate tasks
    kraken_project.do("default1", VoidTask, default=True)
    kraken_project.do("default2", VoidTask, default=True)
    kraken_project.do("task_from_group_g1", VoidTask, group="g1")
    kraken_project.do("other_task_from_group_g1", VoidTask, group="g1")
    kraken_project.do("no_group", VoidTask)

    sub_proj = Project("sub_proj", Path(), parent=kraken_project, context=context)
    kraken_project.add_child(sub_proj)
    sub_proj.do("subproject_task", VoidTask, default=True)
    sub_proj.do("subproject_task_in_group", VoidTask, group="g1")
    sub_proj.do("subproject_task2", VoidTask)

    # Search for tasks from their addresses
    tasks = context.resolve_tasks(["default1"])
    assert len(tasks) == 1

    tasks = context.resolve_tasks(["subproject_task"])
    assert len(tasks) == 1

    with raises(AddressResolutionError):
        context.resolve_tasks([":subproject_task"])

    tasks = context.resolve_tasks(["g1"])
    assert len(tasks) == 2

    tasks = context.resolve_tasks([":g1"])
    assert len(tasks) == 1

    tasks = context.resolve_tasks(["defa*"])
    assert len(tasks) == 2

    # Search for default tasks...
    # ...in the current project
    default_tasks = context.resolve_tasks([":"])
    default_voidtasks = [task for task in default_tasks if type(task) == VoidTask]
    assert len(default_voidtasks) == 2
    assert default_voidtasks[0].name == "default1"
    assert default_voidtasks[1].name == "default2"

    # ...and in subprojects only
    default_tasks = context.resolve_tasks([":**:"])
    default_voidtasks = [task for task in default_tasks if type(task) == VoidTask]
    assert len(default_voidtasks) == 1
    assert default_voidtasks[0].name == "subproject_task"

    with raises(TaskResolutionException):
        context.resolve_tasks([""])

    nothing = context.resolve_tasks([])
    assert len(nothing) == 0
