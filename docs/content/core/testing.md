# Writing tests

This document describes how to write tests for Kraken tasks.

## Use Pytest fixtures

The `kraken-core` package provides the `kraken_ctx: Context` and `kraken_project: Project` fixtures that you can use
in your unit tests. They provide a fresh `kraken.core.Context` and `kraken.core.Project`, respectively, each pointing
to a temporary directory that is automatically cleaned up after the test. The `kraken_project` fixture is automatically
the `Context.root_project` of the `kraken_ctx`.

## Keep it simple

You can do the whole shebang of running `kraken_ctx.execute([":mytask"])` from inside a unit test, but if you want to
test only the behaviour of a single task, it is usually better to just call `task.execute()` directly. Note that if
your task does rely on it's `task.finalize()` and `task.prepare()` method being called, make sure you do that as well.

## Use output properties

Checking the status returned by `task.execute()` is a good way to see if the task returned the result you expected, but
sometimes you may want to get some finer grained information about what happened during the execution. It often makes
sense to export that information form the task's `execute()` method as output properties. In many cases, it is also
convenient for users of the task to have access to these results.

```py
class MyCustomTask(Task):
    some_input: Property[str]
    some_output: Property[list[str]] = Property.output()

    def execute(self) -> TaskStatus:
        self.some_output.set([self.some_input.get()])
        return TaskStatus.succeeded()
```

And then in the unit test:

```py
def test__MyCustomTask__can_do_cool_things(kraken_project: Project) -> None:
    task = kraken_project.do("mytask", MyCustomTask)
    task.some_property.set("foobar")
    status = task.execute()
    assert status == TaskStatus.succeeded()
    assert task.some_output.get() == ["foobar"]
```
