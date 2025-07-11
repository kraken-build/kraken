import inspect
import os
import sys
from collections.abc import Iterable
from dataclasses import MISSING, dataclass, field, fields
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Literal, Mapping, TypeVar, cast, overload

import cyclopts
from typing_extensions import Self

if TYPE_CHECKING:
    from kraken.core.system.context import Context
    from kraken.core.system.graph import TaskGraph
    from kraken.core.system.task import Task

T_Options = TypeVar("T_Options", bound="AspectOptions")


@dataclass
class AspectOptions:
    pass


@dataclass
class AspectBase(Generic[T_Options]):
    """
    Aspects provide a common interface for tasks that share a common goal.

    An "aspect" is a trait that can be implemented by Kraken tasks, providing a common command-line interface for
    different tasks that achieve the same goal to some extent. A task can implement more than one aspect at a time.

    Aspects provide an alternative way to the `kraken build` command to execute tasks, giving some level of
    configurability through command-line arguments that can otherwise only be achieved if the intended tasks
    support special environment variables.

    Take the [`LintAspect`][LintAspect] for example, which represents a superset of tasks that perform linting
    on the code in a project. The aspect allows you to run `kraken lint` and configure it with the options that
    are defined by the aspect.

    An aspect's command-line interface is defnied by a dataclass on the class level named `Options`. This dataclass
    is converted to a command-line interface using the `cyclopts` module. It is required that an override of the
    `Options` dataclass is a subclass of [`AspectOptions`][AspectOptions]. The `Options` dataclass is defined by
    passing the `options_class` meta argument on class creation, like so:

    ```python
    from kraken.core.aspect import Aspect, AspectOptions

    class MyAspect(Aspect["MyAspect.Options"]):

        @dataclass
        class Options(AspectOptions):
            my_option: str = "default_value"

        class Implements: ...
    ```
    """

    Options: ClassVar[type[AspectOptions]]

    Implements: ClassVar[type[Any] | None] = None
    """
    Subclasses can define their own `Implements` class. If set, the default implementation of [select_tasks()] will
    flter tasks to those that inherit from this `Implements` class.
    """

    options: T_Options

    def __init_subclass__(cls, options_class: type[T_Options] | None = None, **kwargs: Any) -> None:
        if options_class is not None:
            cls.Options = cast(type[AspectOptions], options_class)
        super().__init_subclass__(**kwargs)

    @overload
    @classmethod
    def parse_options(
        cls,
        args: list[str],
        name: str | None = None,
        help: str | None = None,
        exit_on_error: Literal[True] = True,
        exit_on_help: bool = True,
        print_error: bool = True,
        env: Mapping[str, str] | None = None,
    ) -> T_Options: ...

    @overload
    @classmethod
    def parse_options(
        cls,
        args: list[str],
        name: str | None = None,
        help: str | None = None,
        exit_on_error: bool = True,
        exit_on_help: bool = True,
        print_error: bool = True,
        env: Mapping[str, str] | None = None,
    ) -> T_Options | None: ...

    @classmethod
    def parse_options(
        cls,
        args: list[str],
        name: str | None = None,
        help: str | None = None,
        exit_on_error: bool = True,
        exit_on_help: bool = True,
        print_error: bool = True,
        env: Mapping[str, str] | None = None,
    ) -> T_Options | None:
        return cast(
            T_Options | None,
            parse_options(
                args,
                cls.Options,
                name=name or cls.__class__.__name__,
                help=help or cls.Options.__doc__,
                exit_on_error=exit_on_error,
                exit_on_help=exit_on_help,
                print_error=print_error,
                env=env,
            ),
        )

    @classmethod
    def current(cls) -> Self | None:
        """
        Returns the current aspect as configured in the current context, if any.
        """

        from kraken.core.system.context import Context

        return Context.current().aspect(cls)

    @classmethod
    def current_options(cls) -> T_Options | None:
        """
        Just like [current], but returns the aspect's options directly.
        """

        aspect = cls.current()
        return aspect.options if aspect else None

    def select_tasks(self, context: "Context", graph: "TaskGraph") -> Iterable["Task"]:
        if self.Implements is None:
            return
        for task in graph.root.tasks():
            if isinstance(task, self.Implements) and task.aspect_applies(self):
                yield task


Aspect = AspectBase[Any]


@overload
def parse_options(
    args: list[str],
    options_class: type[T_Options],
    name: str | None = None,
    help: str | None = None,
    exit_on_error: Literal[True] = True,
    exit_on_help: bool = True,
    print_error: bool = True,
    env: Mapping[str, str] | None = None,
) -> T_Options: ...


@overload
def parse_options(
    args: list[str],
    options_class: type[T_Options],
    name: str | None = None,
    help: str | None = None,
    exit_on_error: bool = True,
    exit_on_help: bool = True,
    print_error: bool = True,
    env: Mapping[str, str] | None = None,
) -> T_Options | None: ...


def parse_options(
    args: list[str],
    options_class: type[T_Options],
    name: str | None = None,
    help: str | None = None,
    exit_on_error: bool = True,
    exit_on_help: bool = True,
    print_error: bool = True,
    env: Mapping[str, str] | None = None,
) -> T_Options | None:
    """
    Create a command-line options parser for the given options class.

    Returns `None` if the `--help` option is passed.
    """

    parameters: list[inspect.Parameter] = []

    for field_ in fields(options_class):
        positional = field_.metadata.get("positional", False)
        parameters.append(
            inspect.Parameter(
                name=field_.name,
                kind=inspect.Parameter.POSITIONAL_ONLY if positional else inspect.Parameter.KEYWORD_ONLY,
                default=field_.default
                if field_.default is not MISSING
                else field_.default_factory()
                if field_.default_factory is not MISSING
                else inspect.Parameter.empty,
                annotation=field_.type,
            )
        )

    result: T_Options | None = None

    def options_parser(*args: Any, **kwargs: Any) -> None:
        """
        Create an instance of the options class with the given arguments.
        """

        nonlocal result
        result = options_class(*args, **kwargs)

    options_parser.__signature__ = inspect.Signature(parameters)  # type: ignore[attr-defined]
    options_parser.__doc__ = help or options_class.__doc__

    # HACK: Maybe there is a better way to pass environment variables to cyclopts?
    try:
        env_copy: Mapping[str, str] | None = None
        if env is not None:
            env_copy = os.environ.copy()
            os.environ.clear()
            os.environ.update(env)

        app = cyclopts.App(name=name or options_class.__name__, version_flags=[])
        app.default(options_parser)
        app(args, exit_on_error=exit_on_error, print_error=print_error)
    finally:
        if env is not None:
            assert env_copy is not None
            os.environ.clear()
            os.environ.update(env_copy)

    if exit_on_help and result is None:
        sys.exit(0)
    return result


@dataclass
class LintAspect(AspectBase["LintAspect.Options"]):
    """
    An aspect that represents a superset of tasks that perform linting on the code in a project.
    """

    @dataclass
    class Options(AspectOptions):
        """
        Perform linting on the code in a project.

        Linting concerns the process of checking the code for semantic, stylistic and specific formatting issues that could
        lead to bugs or make the code harder to read and maintain. This aspect provides a common interface for tasks that
        implement such checks.

        Parameters
        ----------
        paths:
            Narrow the set of files to lint down to these paths. If not specified, it's equivalent of passing "."
        fix:
            Automatically fix issues where possible.
        unsafe_fix:
            Automatically fix issues where possible, even if it may lead to unsafe changes. This is a more aggressive
            option and should be used with caution.
        """

        paths: list[str] = field(default_factory=lambda: ["."], metadata={"positional": True})
        fix: bool = False
        unsafe_fix: bool = False

    class Implements:
        """
        Tasks should additionally inherit from this class to denote that they implement the lint aspect.
        """


@dataclass
class FmtAspect(AspectBase["CheckAspect.Options"]):
    """
    An aspect that represents a superset of tasks that perform formatting on files.
    """

    @dataclass
    class Options(AspectOptions):
        """
        Perform formatting on code in the project.

        Parameters
        ----------
        paths:
            Narrow the set of files to format down to these paths. If not specified, it's equivalent of passing "."
        """

        paths: list[str] = field(default_factory=lambda: ["."], metadata={"positional": True})

    class Implements:
        """
        Tasks should additionally inherit from this class to denote that they implement the `fmt` aspect.
        """


@dataclass
class CheckAspect(AspectBase["CheckAspect.Options"]):
    """
    An aspect that represents a superset of tasks that perform type checking on code.
    """

    @dataclass
    class Options(AspectOptions):
        """
        Perform type checking on the code in a project.

        Type checking concerns itself only with the correctness of code with respect to its type definitions.

        Parameters
        ----------
        paths:
            Narrow the set of files to check down to these paths. If not specified, it's equivalent of passing "."
        """

        paths: list[str] = field(default_factory=lambda: ["."], metadata={"positional": True})

    class Implements:
        """
        Tasks should additionally inherit from this class to denote that they implement the check aspect.
        """


ASPECTS: dict[str, type[Aspect]] = {
    "fmt": FmtAspect,
    "lint": LintAspect,
    "check": CheckAspect,
}
