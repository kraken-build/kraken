"""
**Experimental.**

Aspects provide a new way to interface with Kraken tasks. An aspects represents a common goal that is implemented by
many tasks and can be used to selectively execute one or many similar tasks with common options that can be specified
on the command-line.
"""

import inspect
import logging
import os
import shlex
import sys
from collections.abc import Iterable, Sequence
from dataclasses import MISSING, dataclass, field, fields
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Generic,
    Literal,
    Mapping,
    TypeGuard,
    TypeVar,
    cast,
    overload,
)

import attrs
import cyclopts
from typeapi import AnnotatedTypeHint, ClassTypeHint, TypeHint
from typing_extensions import Self

from kraken.core.system.errors import BuildError
from kraken.core.system.property import Property

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

    from kraken.core.system.context import Context
    from kraken.core.system.graph import TaskGraph
    from kraken.core.system.task import Task

logger = logging.getLogger(__name__)
T = TypeVar("T")
T_Dataclass = TypeVar("T_Dataclass", bound="DataclassInstance")
T_Options = TypeVar("T_Options", bound="AspectOptions")
T_AspectWithPathsFilter_Options = TypeVar("T_AspectWithPathsFilter_Options", bound="_AspectWithPathsFilter.Options")


@dataclass
class AspectOptions:
    """Base class for aspect options."""

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

    Take the [`LintAspect`][kraken.core.system.aspect.LintAspect] for example, which represents a superset of tasks
    that perform linting on the code in a project. The aspect allows you to run `kraken lint` and configure it with
    the options that are defined by the aspect.

    An aspect's command-line interface is defnied by a dataclass on the class level named `Options`. This dataclass
    is converted to a command-line interface using the `cyclopts` module. It is required that an override of the
    `Options` dataclass is a subclass of [`AspectOptions`][kraken.core.AspectOptions]. The `Options` dataclass is
    defined by passing the `options_class` meta argument on class creation, like so:

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

        # Need this to (1) filter out the case where the class is defined in this module and (2) to prevent
        # importing the Task class before this module is fully imported to prevent a cyclic import issue.
        if cls.__module__ != __name__:
            from kraken.core import Task

            if issubclass(cls, Task):
                raise RuntimeError(
                    f"you're inheriting a Task implementation from {cls.__name__}, you probably want "
                    f"to inherit from {cls.__name__}.Implements instead?"
                )
        if "Implements" not in vars(cls):
            raise RuntimeError(f"missing {cls.__name__}.Implements class")

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
                name=name or cls.__name__,
                help=help,
                exit_on_error=exit_on_error,
                exit_on_help=exit_on_help,
                print_error=print_error,
                env=env,
            ),
        )

    @classmethod
    def current(cls, for_task: "Task") -> Self | None:
        """
        Returns the current aspect as configured in the current context, if any.
        """

        from kraken.core.system.context import Context

        return Context.current().aspect(cls, for_task)

    @classmethod
    def current_options(cls, for_task: "Task") -> T_Options | None:
        """
        Just like [current], but returns the aspect's options directly.
        """

        aspect = cls.current(for_task)
        return aspect.options if aspect else None

    def init(self, context: "Context") -> None:
        """Called when the aspect is registered to the context."""

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
class _AspectWithPathsFilter(AspectBase["T_AspectWithPathsFilter_Options"], Generic[T_AspectWithPathsFilter_Options]):
    """
    Base class for aspects that have a `paths` field in the options that take paths that should be considered
    relative to the original working directory that Kraken is invoked from. Since kraken will change directory
    into the project root directory, we post-process the paths to point to the original working directory which
    is stored in [`Context.original_working_directory`][kraken.core.Context.original_working_directory].
    """

    class Implements:
        pass

    @dataclass
    class Options(AspectOptions):
        paths: list[Path] = field(default_factory=lambda: [Path(".")], metadata={"positional": True})

    def init(self, context: "Context") -> None:
        self.options.paths = [context.original_working_directory / path for path in self.options.paths]
        return super().init(context)


@dataclass
class LintAspect(_AspectWithPathsFilter["LintAspect.Options"]):
    """
    An aspect that represents a superset of tasks that perform linting on the code in a project.
    """

    @dataclass
    class Options(_AspectWithPathsFilter.Options):
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

        fix: bool = False
        unsafe_fix: bool = False

    class Implements:
        """
        Tasks should additionally inherit from this class to denote that they implement the lint aspect.
        """


@dataclass
class FmtAspect(_AspectWithPathsFilter["FmtAspect.Options"]):
    """
    An aspect that represents a superset of tasks that perform formatting on files.
    """

    @dataclass
    class Options(_AspectWithPathsFilter.Options):
        """
        Perform formatting on code in the project.

        Parameters
        ----------
        paths:
            Narrow the set of files to format down to these paths. If not specified, it's equivalent of passing "."
        check:
            Instead of formatting files, only whether the files _would_ be formatted, and error if there are any.
        """

        check: bool = False

    class Implements:
        """
        Tasks should additionally inherit from this class to denote that they implement the `fmt` aspect.
        """


@dataclass
class CheckAspect(_AspectWithPathsFilter["CheckAspect.Options"]):
    """
    An aspect that represents a superset of tasks that perform type checking on code.
    """

    @dataclass
    class Options(_AspectWithPathsFilter.Options):
        """
        Perform type checking on the code in a project.

        Type checking concerns itself only with the correctness of code with respect to its type definitions.

        Parameters
        ----------
        paths:
            Narrow the set of files to check down to these paths. If not specified, it's equivalent of passing "."
        """

    class Implements:
        """
        Tasks should additionally inherit from this class to denote that they implement the check aspect.
        """


@dataclass
class TestAspect(_AspectWithPathsFilter["TestAspect.Options"]):
    """
    An aspect that represents a superset of tasks that execute tests on code.
    """

    @dataclass
    class Options(_AspectWithPathsFilter.Options):
        """
        Execute tests in your code base.

        Parameters
        ----------
        paths:
            Narrow the set test sources down to these paths. If not specified, it's equivalent of passing "."
        filter:
            One or more tokens to filter by. Tests that include either one of these tokens will be run.
        """

        filter: list[str] = field(default_factory=lambda: [])

        def format_filters(self) -> str:
            parts: list[str] = []
            if self.paths:
                parts += map(os.fspath, self.paths)
            if self.filter:
                parts += [f"--filter={filter}" for filter in self.filter]
            return shlex.join(parts)

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

        When the [`TestAspect`][kraken.core.TestAspect] is active and a filter is provided, test tasks should permit
        when no tasks where run instead of returning [TaskStatus.FAILED][kraken.core.TaskStatusType.FAILED]. The
        [`TestAspect`][kraken.core.TestAspect] will then check across all tasks that were run whether at least one task
        has run at least one test.
        """

    def after_execute_graph(self, context: "Context", graph: "TaskGraph") -> None:
        from kraken.core.system.task import TaskStatus

        # If we're using filters, test tasks might fail when they found no matching tests. This is ok if at least
        # one test task did not fail.
        if self.options.filter or self.options.paths:
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
                    reason = f"specified filters ({self.options.format_filters()}) matched no tests"
                raise BuildError(failed_tasks, reason=reason)


@dataclass
class BuildAspect(AspectBase["BuildAspect.Options"]):
    """
    This aspect can be used to perform the building of an artifact (such as an executable or archive). If target
    specified in the options can be a Kraken task or a path. If a path is specified, Kraken will search for the path
    in any of the output properties (note that this only works for properties that are not computed and depend on
    unpopulated properties).
    """

    class Implements:
        pass

    @dataclass
    class Options(AspectOptions):
        """
        Execute a task or build a given artifact.

        Support of the options depends on the selected target.

        Parameters
        ----------
        target:
            A single Kraken tasks and/or output path. If a basic name is used (e.g. `main`), it will be treated as a
            target name. Use e.g. `./main` to reference a local file called `main`.

        outfile:
            When selecting a task that produces a single output file, it may support altering the path it is placed
            in via this option. Some tasks may produce a folder instead.

        release:
            Some tasks may distinguish between debug and release builds. Using this option is equal to setting
            `--build-mode=release`.

        debug:
            Some tasks may distinguish between debug and release builds. Using this option is equal to setting
            `--build-mode=debug`.

        build-mode:
            An arbitrary string that the selected task can interpret to modify its build behaviour. Example values
            are `release` and `debug`.

        symlink:
            Define whether symlinks should be created when writing the result paths of the task or not.
        """

        target: str = field(metadata={"positional": True})

        outfile: Path | None = None

        release: bool = False
        debug: bool = False
        build_mode: str | None = None

        symlink: bool | None = None

        def __post_init__(self) -> None:
            if self.build_mode and self.release:
                raise ValueError("--build-mode and --release cannot be combined")
            if self.build_mode and self.debug:
                raise ValueError("--build-mode and --debug cannot be combined")
            if self.release and self.debug:
                raise ValueError("--release and --debug cannot be combined")

        @overload
        def get_build_mode(self, fallback: None = None) -> Literal["release", "debug"] | str | None: ...

        @overload
        def get_build_mode(self, fallback: T) -> Literal["release", "debug"] | str | T: ...

        def get_build_mode(self, fallback: T | None = None) -> Literal["release", "debug"] | str | T | None:
            if self.release:
                return "release"
            if self.debug:
                return "debug"
            if self.build_mode:
                return self.build_mode
            return fallback

    @staticmethod
    def _is_path_property_type(hint: TypeHint) -> bool:
        """
        A helper method to determine if the give type hint, representing the inner type of a
        [`Property`][kraken.core.Property], represents a [`PathLike`][os.PathLike] or a sequence of such.

        >>> from pathlib import Path, PosixPath, WindowsPath
        >>> from typing import Sequence
        >>> from typeapi import TypeHint
        >>> BuildAspect._is_path_property_type(TypeHint(Path))
        True
        >>> BuildAspect._is_path_property_type(TypeHint(PosixPath))
        True
        >>> BuildAspect._is_path_property_type(TypeHint(WindowsPath))
        True
        >>> BuildAspect._is_path_property_type(TypeHint(list[Path]))
        True
        >>> BuildAspect._is_path_property_type(TypeHint(tuple[Path]))
        True
        >>> BuildAspect._is_path_property_type(TypeHint(Sequence[Path]))
        True
        >>> BuildAspect._is_path_property_type(TypeHint(str))
        False
        >>> BuildAspect._is_path_property_type(TypeHint(list[str]))
        False
        >>> BuildAspect._is_path_property_type(TypeHint(tuple[str]))
        False
        """

        def _unwrap(hint: TypeHint) -> TypeHint:
            if isinstance(hint, AnnotatedTypeHint):
                hint = TypeHint(hint.type)
            return hint

        hint = _unwrap(hint)
        if not isinstance(hint, ClassTypeHint):
            return False

        if issubclass(hint.type, Sequence) and len(hint.args) > 0:
            inner_type = _unwrap(TypeHint(hint.args[0]))
            if not isinstance(inner_type, ClassTypeHint):
                return False

            return issubclass(inner_type.type, os.PathLike)

        elif issubclass(hint.type, os.PathLike):
            return True

        return False

    @staticmethod
    def _is_path_property(
        prop: Property[Any],
    ) -> TypeGuard[Property[os.PathLike[str]] | Property[Sequence[os.PathLike[str]]]]:
        return BuildAspect._is_path_property_type(prop.item_type)

    @staticmethod
    def _search_for_task_producing(context: "Context", path: Path) -> "list[Task]":
        path = path.resolve()
        result = []

        for project in context.iter_projects():
            for task in project.tasks().values():
                produces: list[os.PathLike[str]] = []
                for prop in task.get_properties():
                    if not task.__schema__[prop.name].is_output:
                        continue
                    if not BuildAspect._is_path_property(prop):
                        continue

                    try:
                        value = prop.get()
                    except Property.Deferred:
                        logger.debug(
                            "could not check task %r property %r as it is deferred",
                            str(task.address),
                            prop.name,
                        )
                        continue

                    if isinstance(value, os.PathLike):
                        produces.append(value)
                    elif isinstance(value, Sequence):
                        produces.extend(value)
                    else:
                        logger.warning(  # type: ignore[unreachable]
                            "got unexpected value from task %r property %r, expected PathLike|Sequence[PathLike], got %r",
                            str(task.address),
                            prop.name,
                            value,
                        )

                for produced_path in map(lambda x: Path(x).resolve(), produces):
                    if produced_path.is_relative_to(path) or produced_path == path:
                        result.append(task)

        return result

    def init(self, context: "Context") -> None:
        if self.options.outfile:
            self.options.outfile = context.original_working_directory / self.options.outfile
        return super().init(context)

    def select_tasks(self, context: "Context", graph: "TaskGraph") -> Iterable["Task"]:
        from kraken.core.system.task import GroupTask

        # Determine if a Kraken task or output path is selected.
        target = self.options.target
        if "/" in target or "\\" in target:
            # Find the task(s) that produce the specified output file.
            tasks = self._search_for_task_producing(context, Path(target))
        else:
            tasks = context.resolve_tasks([target], relative_to=context.focus_project)

        # Ignore group tasks, they could be accidentally selected when specifying a target.
        tasks = [t for t in tasks if not isinstance(t, GroupTask)]
        implements = [t for t in tasks if isinstance(t, BuildAspect.Implements)]
        not_implements = [t for t in tasks if not isinstance(t, BuildAspect.Implements)]

        if not implements:
            raise ValueError(f"no task matched the specified target: {target}")

        if len(implements) > 1:
            raise ValueError(f"more than one task matched the specified target: {target}")

        if not_implements:
            logger.warning(
                'Your target (%s) matched one task that implements the "build" aspect, but {} other(s) that does not. '
                "If these tasks in the future implement the aspect, the same command will fail because the aspect "
                "supports only a single task. Matching tasks that are ignored: %s",
                target,
                ", ".join(map(lambda t: str(t.address), tasks)),
            )

        return tasks


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
        tasks = context.resolve_tasks([self.options.task], relative_to=context.focus_project)
        if not tasks:
            return []  # Caller will handle the error
        if len(tasks) > 1:
            raise BuildError(tasks, reason="not more than one task can be selected with the run aspect")
        return tasks


ASPECTS: dict[str, type[Aspect]] = {
    "build": BuildAspect,
    "fmt": FmtAspect,
    "lint": LintAspect,
    "check": CheckAspect,
    "test": TestAspect,
    "invoke": RunAspect,  # "run" is currently shadowed by the original "kraken run" command
}
"""
Maps the aspect's subcommand name for the Kraken CLI to the aspect class.
"""
