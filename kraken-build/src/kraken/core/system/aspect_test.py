import inspect
from dataclasses import dataclass, field
from typing import Annotated, Any

import cyclopts
from cyclopts import MissingArgumentError, Parameter
from pytest import raises

from kraken.core.system.aspect import AspectOptions, build_signature_from_dataclass, parse_options


def test_parse_options() -> None:
    @dataclass(kw_only=True)
    class MyAspectOptions(AspectOptions):
        without_default: str
        with_default: str = "default_value"
        with_help: Annotated[str, Parameter(env_var="WITH_HELP")] = "no"

    with raises(MissingArgumentError) as excinfo:
        options = parse_options([], MyAspectOptions, exit_on_error=False, print_error=False)
    assert str(excinfo.value) == 'Parameter "--without-default" requires an argument.'

    options = parse_options(["--without-default", "foo"], MyAspectOptions, exit_on_error=False)
    assert options == MyAspectOptions(without_default="foo", with_default="default_value")

    options = parse_options(
        ["--without-default", "foo"],
        MyAspectOptions,
        exit_on_error=False,
        env={"WITH_HELP": "yes"},
    )
    assert options == MyAspectOptions(without_default="foo", with_default="default_value", with_help="yes")


def test_parse_options_varargs() -> None:
    @dataclass
    class MyAspectOptions(AspectOptions):
        task: str = field(metadata={"positional": True})
        args: list[str] = field(metadata={"positional": True})

    options = parse_options([":task", "arg1", "arg2"], MyAspectOptions, exit_on_error=False, print_error=False)
    assert options == MyAspectOptions(":task", ["arg1", "arg2"])


def test_parse_options_varargs_with_hyphen() -> None:
    @dataclass
    class MyAspectOptions(AspectOptions):
        task: str = field(metadata={"positional": True})
        args: list[str] = field(metadata={"positional": True})

    input_args = [":task", "arg1", "--arg2"]

    # Test that the Python function signature and mapping of positional to keyword arguments that we build
    # is what we expect.
    signature, positional_map = build_signature_from_dataclass(MyAspectOptions)
    assert signature == inspect.Signature(
        [
            inspect.Parameter(name="task", kind=inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
            inspect.Parameter(
                name="args",
                kind=inspect.Parameter.VAR_POSITIONAL,
                annotation=Annotated[str, cyclopts.Parameter(allow_leading_hyphen=True)],
            ),
        ],
        return_annotation=None,
    )
    assert positional_map == {"task": 0, "args": slice(1, None)}

    # Compare this with a corresponding signature directly from a Python function.
    parsed_args: tuple[str, ...] | None = None

    def same_signature(task: str, *args: Annotated[str, cyclopts.Parameter(allow_leading_hyphen=True)]) -> None:
        nonlocal parsed_args
        parsed_args = args

    assert inspect.signature(same_signature) == signature

    # Test parsing the args with regular cyclopts.
    app = cyclopts.App()
    app.default(same_signature)
    app(input_args, exit_on_error=False, print_error=False)
    assert parsed_args == ("arg1", "--arg2")

    # Test parsing with constructed signature.
    parsed_args = None

    def constructed_signature(*args: Any, **kwargs: Any) -> None:
        nonlocal parsed_args
        parsed_args = args[positional_map["args"]]

    constructed_signature.__signature__ = signature  # type: ignore[attr-defined]
    constructed_signature.__annotations__ = {}
    app = cyclopts.App()
    app.default(constructed_signature)
    app(input_args, exit_on_error=False, print_error=False)
    assert parsed_args == ("arg1", "--arg2")

    # Test parsing with end-to-end parsing function.
    options = parse_options(input_args, MyAspectOptions, exit_on_error=False, print_error=False)
    assert options == MyAspectOptions(":task", ["arg1", "--arg2"])
