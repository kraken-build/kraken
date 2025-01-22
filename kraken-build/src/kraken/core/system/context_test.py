from pathlib import Path

from pytest import raises

from kraken.core.address import AddressResolutionError
from kraken.core.system.context import Context, TaskResolutionException
from kraken.core.system.project import Project
from kraken.core.system.task import VoidTask


def test__Context__resolve_tasks(kraken_ctx: Context, kraken_project: Project) -> None:
    # Generate tasks
    kraken_project.task("default1", VoidTask, default=True)
    kraken_project.task("default2", VoidTask, default=True)
    kraken_project.task("task_from_group_g1", VoidTask, group="g1")
    kraken_project.task("other_task_from_group_g1", VoidTask, group="g1")
    kraken_project.task("no_group", VoidTask)

    sub_proj = Project("sub_proj", Path(), parent=kraken_project, context=kraken_ctx)
    kraken_project.add_child(sub_proj)
    sub_proj.task("subproject_task", VoidTask, default=True)
    sub_proj.task("subproject_task_in_group", VoidTask, group="g1")
    sub_proj.task("subproject_task2", VoidTask)

    # Search for tasks from their addresses
    tasks = kraken_ctx.resolve_tasks(["default1"])
    assert len(tasks) == 1

    tasks = kraken_ctx.resolve_tasks(["subproject_task"])
    assert len(tasks) == 1

    with raises(AddressResolutionError):
        kraken_ctx.resolve_tasks([":subproject_task"])

    tasks = kraken_ctx.resolve_tasks(["g1"])
    assert len(tasks) == 2

    tasks = kraken_ctx.resolve_tasks([":g1"])
    assert len(tasks) == 1

    tasks = kraken_ctx.resolve_tasks(["defa*"])
    assert len(tasks) == 2

    # Search for default tasks...
    # ...in the current project
    default_tasks = kraken_ctx.resolve_tasks([":"])
    default_voidtasks = [task for task in default_tasks if isinstance(task, VoidTask)]
    assert len(default_voidtasks) == 2
    assert default_voidtasks[0].name == "default1"
    assert default_voidtasks[1].name == "default2"

    # ...and in subprojects only
    default_tasks = kraken_ctx.resolve_tasks([":**:"])
    default_voidtasks = [task for task in default_tasks if isinstance(task, VoidTask)]
    assert len(default_voidtasks) == 1
    assert default_voidtasks[0].name == "subproject_task"

    with raises(TaskResolutionException):
        kraken_ctx.resolve_tasks([""])

    nothing = kraken_ctx.resolve_tasks([])
    assert len(nothing) == 0


def test__Context__resolve_tasks__can_resolve_optional_tasks(kraken_ctx: Context, kraken_project: Project) -> None:
    """
    Tests that optional tasks can be resolved using the #Context.resolve_tasks() method.
    """

    sub1 = kraken_project.subproject("sub1", mode="empty")
    sub2 = kraken_project.subproject("sub2", mode="empty")

    publish_task = sub2.task("publishSomething", VoidTask, group="publish")
    assert sub2.group("publish").tasks == [sub2.task("publishSomething")]

    # Note: A "publish" task group already exists on all projects by default.

    # When we resolve the address selector "publish", it matches all tasks named "publish" in all projects.
    tasks = kraken_ctx.resolve_tasks(["publish"])
    assert set(tasks) == {
        kraken_project.group("publish"),
        sub1.group("publish"),
        sub2.group("publish"),
    }

    # When resolving it inside a sub project, it matches only the tasks in that sub project.
    tasks = kraken_ctx.resolve_tasks(["publish"], relative_to=sub2)
    assert set(tasks) == {sub2.group("publish")}

    #
    # Let's also test the tasks that the TaskGraph will contain.
    #

    # When we pass all publish tasks, they are definitely included in the graph + the members of those groups.
    expanded_tasks = set(kraken_ctx.get_build_graph(kraken_ctx.resolve_tasks(["publish"])).tasks())
    assert set(expanded_tasks) == {
        kraken_project.group("publish"),
        sub1.group("publish"),
        sub2.group("publish"),
        publish_task,
    }

    # When we pass the root publish task, only that group is in the graph because that group has no members.
    expanded_tasks = set(kraken_ctx.get_build_graph([kraken_project.task("publish")]).tasks())
    assert set(expanded_tasks) == {kraken_project.group("publish")}

    # When we pass the publish task from the sub project that contains a task, those are in the graph.
    expanded_tasks = set(kraken_ctx.get_build_graph([sub2.task("publish")]).tasks())
    assert set(expanded_tasks) == {sub2.group("publish"), publish_task}
