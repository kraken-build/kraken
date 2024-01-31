# Tasks

## Overview

Kraken describes the build graph using tasks which can have relationships and properties. Tasks are
described in code using a subclass of {@pylink kraken.core.system.task.Task}.

```py title="hello_task.py"
from kraken.core import Property, Task

class HelloTask(Task):
    subject: Property[str]
    
    def execute(self) -> None:
        print("Hello,", self.subject.get())
```

Relationships between tasks can be formed with three methods:

1. Explicitly using {@pylink kraken.core.system.task.Task.depends_on} and {@pylink kraken.core.system.task.Task.required_by}
2. By connecting the property of one task to that of another (e.g. using {@pylink kraken.core.system.property.Property.set})
3. Overriding {@pylink kraken.core.system.task.Task.get_relationships} in the task subclass

!!! info

    Unlike other build systems, Kraken doesn't really care about files and does not treat that as build targets.
    An analogy to understand what Kraken does is this: If you were to build a C++ project, you will still use
    CMake or any other C++ build tool, and Kraken may invoke that build tool for you among other things.

!!! warning

    As a side effect of this, Kraken is currently not particularly good at _not_ running a task that may actually
    not need to run another time because it would not perform any new work.

To read more about properties, see {@pylink kraken.core.system.property.Property}.

### Task outputs

A task property can be marked as an output property. The task is then expected to populate its value in
{@pylink kraken.core.system.task.Task.execute} (or {@pylink kraken.core.system.task.Task.prepare} if the task decides that
it does not need to run).

```py title="zip_task.py"
from kraken.core import Property, Task
from pathlib import Path
from typing import Union

class ZipTask(Task):
    files: Property[List[Path]]
    output_file: Property[Path] = Property.output()

    # ...
```

Outputs of a task can be queried and used as inputs by other tasks. For example, if you receive a task and you only
know that it delivers some particular type of *Python object* as an "output", you can pick it up without knowing the
exact property. Most commonly, this is done via {@pylink kraken.core.system.project.Project.resolve_tasks}, which allows you to
resolve a set of dependencies by name or address, and then select the properties you are interested in.

```py title="upload_task.py"
from kraken.core import Project

def upload_task(*, name: str, folder_url: str, dependencies: list[str], project: Project | None) -> UploadTask:
    project = project or Project.current()
    task = project.task(name=name, task_type=UploadTask)
    task.files = project.resolve_tasks(dependencies).select(Path).supplier()
    return task
```

There's a bit to unpack here.

1. We use the `Project.current()` static method to retrieve the Kraken project that
    is currently being evaluated unless an explicit project was specified.
2. Then we use the `project.task()` method to create a new task of type `UploadTask` (which is defined
    somewhere else, but not a component delivered by Kraken).
3. The `UploadTask` has a property defined as `files: Property[Sequence[Path]]`, and we pass the `files=...`
    keyword argument to populate it. As a value, we pass a "supplier" object which will return all the `Path`
    objects in output properties of the specified `dependencies`.

!!! important

    You must keep in mind that the project is evaluated in full before any task is executed. It is therefore important
    to model the connection between the outputs of one task and the inputs of another in a lazy fashion. We could not
    successfully use `list(project.resolve_tasks(dependencies).select(Path).all())` here because the output properties
    of the `dependencies` will not have been populated yet.
