import inspect
import logging
import os
import sys
from collections.abc import Iterable
from dataclasses import MISSING, dataclass, field, fields
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Generic, Literal, Mapping, TypeVar, cast, overload

import attrs
import cyclopts
from typeapi import AnnotatedTypeHint, ClassTypeHint, TypeHint
from typing_extensions import Self

from kraken.core.system.errors import BuildError

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

    from kraken.core.system.context import Context
    from kraken.core.system.graph import TaskGraph
    from kraken.core.system.task import Task

logger = logging.getLogger(__name__)
T_Dataclass = TypeVar("T_Dataclass", bound="DataclassInstance")
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
    filter tasks to those that inherit from this `Implements` class.
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

    def after_execute_graph(self, context: "Context", graph: "TaskGraph") -> None:
        pass


Aspect = AspectBase[Any]


@overload
def parse_options(
    args: list[str],
    options_class: type[T_Dataclass],
    name: str | None = None,
    help: str | None = None,
    exit_on_error: Literal[True] = True,
    exit_on_help: bool = True,
    print_error: bool = True,
    env: Mapping[str, str] | None = None,
) -> T_Dataclass: ...


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
    options_class: type[T_Dataclass],
    name: str | None = None,
    help: str | None = None,
    exit_on_error: bool = True,
    exit_on_help: bool = True,
    print_error: bool = True,
    env: Mapping[str, str] | None = None,
) -> T_Dataclass | None:
    """
    Create a command-line options parser for the given options class.

    Returns `None` if the `--help` option is passed.
    """

    result: T_Dataclass | None = None
    signature, positional_map = build_signature_from_dataclass(options_class)

    def options_parser(*args: Any, **kwargs: Any) -> None:
        """
        Create an instance of the options class with the given arguments.
        """

        for field_name, index in positional_map.items():
            if isinstance(index, int) and index >= len(args):
                # Optional positional argument.
                continue

            kwargs[field_name] = args[index]

            # Varargs are only supported for fields annotated as list, but args is a tuple.
            if isinstance(index, slice):
                kwargs[field_name] = list(kwargs[field_name])

        nonlocal result
        result = options_class(**kwargs)

    options_parser.__signature__ = signature  # type: ignore[attr-defined]
    options_parser.__annotations__ = {}  # We need to unset these, other cyclopts will consider them and it breaks.
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


def build_signature_from_dataclass(
    data_class: "type[DataclassInstance]",
) -> tuple[inspect.Signature, dict[str, int | slice]]:
    parameters: list[inspect.Parameter] = []

    positional_index = 0
    positional_map: dict[str, int | slice] = {}

    for field_ in fields(data_class):
        hint = TypeHint(field_.type)

        # Unwrap the Annotated type hint, if any.
        annotations: tuple[Any, ...] = ()
        if isinstance(hint, AnnotatedTypeHint):
            annotations = hint.metadata
            hint = TypeHint(hint.type)

        # If already annotated with a Cyclopts parameter, use it.
        param_cfg = next((x for x in annotations if isinstance(x, cyclopts.Parameter)), None)
        annotations = tuple(x for x in annotations if x is not param_cfg)

        # Determine the parameter kind.
        if field_.metadata.get("positional", False):
            if isinstance(hint, ClassTypeHint) and hint.type is list and field_.default_factory is MISSING:
                # Positional argument typed as a list with no default arguments takes varargs.
                kind: inspect._ParameterKind = inspect.Parameter.VAR_POSITIONAL
                positional_map[field_.name] = slice(positional_index, None)
                param_cfg = (
                    attrs.evolve(param_cfg, allow_leading_hyphen=True)
                    if param_cfg
                    else cyclopts.Parameter(allow_leading_hyphen=True)
                )
                hint = TypeHint(hint.args[0])  # Use item type
            else:
                kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
                positional_map[field_.name] = positional_index
                positional_index += 1
        else:
            kind = inspect.Parameter.KEYWORD_ONLY

        default = (
            field_.default
            if field_.default is not MISSING
            else field_.default_factory()
            if field_.default_factory is not MISSING
            else inspect.Parameter.empty
        )

        # Rebuild the Annotated type hint if needed.
        if param_cfg:
            annotations = (param_cfg, *annotations)
        if annotations:
            hint = TypeHint(Annotated[(hint.hint, *annotations)])

        parameters.append(
            inspect.Parameter(
                name=field_.name,
                kind=kind,
                default=default,
                annotation=hint.hint,
            )
        )

    return inspect.Signature(parameters, return_annotation=None), positional_map


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
class FmtAspect(AspectBase["FmtAspect.Options"]):
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
        check:
            Instead of formatting files, only whether the files _would_ be formatted, and error if there are any.
        """

        paths: list[str] = field(default_factory=lambda: ["."], metadata={"positional": True})
        check: bool = False

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


@dataclass
class TestAspect(AspectBase["TestAspect.Options"]):
    """
    An aspect that represents a superset of tasks that execute tests on code.
    """

    @dataclass
    class Options(AspectOptions):
        """
        Execute tests in your code base.

        Parameters
        ----------
        paths:
            Narrow the set test sources down to these paths. If not specified, it's equivalent of passing "."
        filter:
            One or more tokens to filter by. Tests that include either one of these tokens will be run.
        """

        paths: list[str] = field(default_factory=lambda: ["."], metadata={"positional": True})
        filter: list[str] = field(default_factory=lambda: [])

    class Implements:
        """
        Tasks should additionally inherit from this class to denote that they implement the test aspect.
        """

        TestAspect_failure_reason: Literal["NoTests"] | None = None
        """
        This field must be set by tasks that implement the test aspect after execution to indicate whty the task has
        failed.

        Many individual test tasks would usually error if they can not find a single test to run as it might prompt
        a misconfiguration. However, when filters are applied, it's possible that from a set of many test tasks, only
        some are going to have tests that match the filter, leaving others to not run any tests and usually error.

        When the [TestAspect] is active and a filter is provided, test tasks should permit when no tasks where run
        instead of returning [TaskStatus.FAILED][kraken.core.system.task.TaskStatus.FAILED]. The [TestAspect] will
        then check across all tasks that were run whether at least one task has run at least one test.
        """

    def after_execute_graph(self, context: "Context", graph: "TaskGraph") -> None:
        from kraken.core.system.task import TaskStatus

        # If we're using filters, test tasks might fail when they found no matching tests. This is ok if at least
        # one test task did not fail.
        if self.options.filter:
            ok_tasks = [task for task in graph.tasks(ok=True) if isinstance(task, TestAspect.Implements)]
            failed_tasks = [task for task in graph.tasks(failed=True) if isinstance(task, TestAspect.Implements)]
            for task in failed_tasks:
                if task.TestAspect_failure_reason == "NoTests":
                    new_status = TaskStatus.warning("no tests selected")
                    logger.debug(
                        "Altering status of task %s from %s to %s",
                        task.address,
                        graph.get_status(task),
                        new_status,
                    )
                    graph.set_status(task, new_status, force=True)

            if not ok_tasks:
                reason = None
                if all(t.TestAspect_failure_reason == "NoTests" for t in failed_tasks):
                    reason = "specified --filter matched no tests"
                raise BuildError(failed_tasks, reason=reason)


@dataclass
class RunAspect(AspectBase["RunAspect.Options"]):
    """
    An aspect that can be used to run a single task, optionally appending arguments to the command the task wraps.
    This aspect is usually implemented for build artifacts, allowing you to invoke them. Some tasks may also parse
    the arguments themselves and mutate their behavior accordingly.
    """

    class Implements:
        pass

    @dataclass
    class Options(AspectOptions):
        """
        Invoke a task that represents something runnable and which optionally accepts additional arguments.

        Parameters
        ----------
        task:
            The name of the task to invoke.
        args:
            Additional arguments to pass to the runnable.
        """

        task: str = field(metadata={"positional": True})
        args: list[str] = field(metadata={"positional": True})

    def select_tasks(self, context: "Context", graph: "TaskGraph") -> Iterable["Task"]:
        # TODO: We mgiht need to do something in the context to only reveal the aspect to tasks that
        #       are returned by this method. If the targeted task depends on another that also implements
        #       the "run" aspect, that other task should not be using the aspect.
        tasks = context.resolve_tasks([self.options.task])
        if not tasks:
            return []  # Caller will handle the error
        if len(tasks) > 1:
            raise BuildError(tasks, reason="not more than one task can be selected with the run aspect")
        return tasks


ASPECTS: dict[str, type[Aspect]] = {
    "fmt": FmtAspect,
    "lint": LintAspect,
    "check": CheckAspect,
    "test": TestAspect,
    "invoke": RunAspect,  # "run" is currently shadowed by the original "kraken run" command
}
