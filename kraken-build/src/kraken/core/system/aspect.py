import inspect
import os
from dataclasses import MISSING, dataclass, fields
from typing import Any, ClassVar, Generic, Literal, Mapping, TypeVar, cast, overload

import cyclopts

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

    @dataclass(kw_only=True)
    class MyAspectOptions(AspectOptions):
        my_option: str = "default_value"

    class MyAspect(Aspect, options_class=MyAspectOptions):
        pass
    ```

    It is _strongly_ recommended to set `kw_only=True` to avoid breakage when parameters are added to the
    [`AspectOptions`][AspectOptions] base class with default values in the future.
    """

    Options: ClassVar[type[AspectOptions]]

    options: T_Options

    def __init_subclass__(cls, options_class: type[T_Options] | None = None, **kwargs: Any) -> None:
        cls.Options = cast(
            type[AspectOptions], options_class or getattr(cls, "Options", cast(type[T_Options], AspectOptions))
        )
        super().__init_subclass__(**kwargs)

    @overload
    @classmethod
    def parse_options(
        cls,
        args: list[str],
        name: str | None = None,
        help: str | None = None,
        exit_on_error: Literal[True] = True,
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
                print_error=print_error,
                env=env,
            ),
        )


Aspect = AspectBase[Any]


@overload
def parse_options(
    args: list[str],
    options_class: type[T_Options],
    name: str | None = None,
    help: str | None = None,
    exit_on_error: Literal[True] = True,
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
    print_error: bool = True,
    env: Mapping[str, str] | None = None,
) -> T_Options | None: ...


def parse_options(
    args: list[str],
    options_class: type[T_Options],
    name: str | None = None,
    help: str | None = None,
    exit_on_error: bool = True,
    print_error: bool = True,
    env: Mapping[str, str] | None = None,
) -> T_Options | None:
    """
    Create a command-line options parser for the given options class.

    Returns `None` if the `--help` option is passed.
    """

    parameters: list[inspect.Parameter] = []

    for field in fields(options_class):
        parameters.append(
            inspect.Parameter(
                name=field.name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=field.default if field.default is not MISSING else inspect.Parameter.empty,
                annotation=field.type,
            )
        )

    result: T_Options | None = None

    def options_parser(*args: Any, **kwargs: Any) -> None:
        """
        Create an instance of the options class with the given arguments.
        """

        nonlocal result
        assert not args, "Options parser should not receive positional arguments"
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

    return result


@dataclass(kw_only=True)
class LintAspectOptions(AspectOptions):
    """
    Perform linting on the code in a project.

    Linting concerns the process of checking the code for semantic, stylistic and specific formatting issues that could
    lead to bugs or make the code harder to read and maintain. This aspect provides a common interface for tasks that
    implement such checks.

    Parameters
    ----------
    fix:
        Automatically fix issues where possible.
    unsafe_fix:
        Automatically fix issues where possible, even if it may lead to unsafe changes. This is a more aggressive
        option and should be used with caution.
    """

    fix: bool = False
    unsafe_fix: bool = False


@dataclass
class LintAspect(AspectBase[LintAspectOptions], options_class=LintAspectOptions):
    """
    An example aspect that represents a superset of tasks that perform linting on the code in a project.
    """


ASPECTS: dict[str, type[Aspect]] = {
    "lint": LintAspect,
}
