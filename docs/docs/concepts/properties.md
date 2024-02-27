# Properties

Kraken tasks have properties which are described as class annotations as `Property` types. They function as a lazy
transport mechanism for data between tasks and allows Kraken to automatically establish dependencies between tasks
whose properties are connected.

```py
from kraken.core import Property, Task

class SayHello(Task):
    name: Property[str]

    def execute(self) -> None:
        print("Hello,", self.name.get())

class GetName(Task):
    name: Property[str] = Property.output()

    def execute(self) -> None:
        self.name = "World"
```

## Properties as descriptors

When accessing a property on a task, you get the `Property` object back. When setting a value, you can use it's
`set()` method, or directly assign to the property. This is because properties are descriptors and implement `__get__()` and `__set__()` accordingly.

```py
say_hello = project.task("say_hello", GetName)
say_hello.name.set("World")
say_hello.name = "World"
```

## Output properties

Not much differentiates output properties from normal properties, except that they raise a `Property.Deferred`
exception instead of `Property.Empty` when their `.get()` method is called and they have not been populated with
a value.

In addition, output properties are taken into account when finding task outputs by type using
{@pylink kraken.core.system.task.TaskSet.select}.

## Preferred property types

You should prefer to use a `Property[Sequence[X]]` over a `Property[List[X]]`. This prevents accidental mutation of
the underlying list. The same goes for `Property[Mapping[K, V]]` over `Property[Dict[K, V]]`. It also improves
usability of the property API because you no longer have to cast or convert everything to the explicit type.

A property value can still be mutated by using {@pylink kraken.core.system.property.Property.setmap}. It is a utility
function, combining `map()` and `set()`.

```py
prop: Property[Sequence[str]] = ...
prop.setmap(lambda v: [*v, "new value"])
```
