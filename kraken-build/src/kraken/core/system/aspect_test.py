from dataclasses import dataclass
from typing import Annotated

from cyclopts import MissingArgumentError, Parameter
from pytest import raises

from kraken.core.system.aspect import AspectOptions, parse_options


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
