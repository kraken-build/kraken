import inspect
import types
from dataclasses import Field, dataclass, fields
from pathlib import Path
from typing import Any, ClassVar, Generic, Protocol, Sequence, TypeVar, overload

from kraken.core.address import Address
from kraken.core.system.project import Project
from typeapi import ClassTypeHint, TypeHint

T = TypeVar("T")
T_DataclassInstance = TypeVar("T_DataclassInstance", bound="DataclassInstance")


class DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Field[Any]]]


@dataclass
class SourceInfo:
    """
    Represents information for the source of a target, i.e. where it came from.
    """

    filename: str
    lineno: int


class Target(Generic[T]):
    """
    Base class for targets.
    """

    def __init__(self, name: str, project: Project, data: T, source: SourceInfo) -> None:
        self.name = name
        self.project = project
        self.address = project.address.append(name)
        self.data = data
        self.source = source
        self.dependencies: list[Address] = []


class TargetNotFoundError(Exception):
    def __init__(self, target_name: str, project: Project) -> None:
        super().__init__(f"Target {target_name!r} not found in project {project.address!r}")


class TargetAlreadyExistsError(Exception):
    def __init__(self, target_name: str, project: Project, existing_target: Target[Any]) -> None:
        super().__init__(
            f"A target with the name {target_name!r} already exists in the project {project.address!r}. The other "
            f"target was defined at {existing_target.source.filename}:{existing_target.source.lineno}"
        )


def get_targets(project: Project) -> dict[str, Target[Any]]:
    """
    Returns the targets map for the given project.
    """

    if not hasattr(project, "_targets"):
        project._targets = {}  # type: ignore[attr-defined]

    return project._targets  # type: ignore[attr-defined, no-any-return]


@overload
def get_target(project: Project, target_name: str) -> Target[Any]:
    ...


@overload
def get_target(project: Project, target_name: str, target_type: type[T]) -> Target[T]:
    ...


def get_target(project: Project, target_name: str, target_type: type[T] | None = None) -> Target[Any] | Target[T]:
    targets = get_targets(project)
    if target_name not in targets:
        raise TargetNotFoundError(target_name, project)
    target = targets[target_name]
    if target_type is not None and not isinstance(target, target_type):
        raise TypeError(f"Target {target_name!r} is not of type {target_type.__qualname__!r}")
    return target


def create_target(
    name: str, project: Project, data: T, source: SourceInfo | inspect.FrameInfo | types.FrameType | None
) -> Target[T]:
    if isinstance(source, inspect.FrameInfo):
        source = source.frame
    if isinstance(source, types.FrameType):
        source = SourceInfo(source.f_code.co_filename, source.f_lineno)
    if source is None:
        source = SourceInfo("<unknown>", 0)
    assert isinstance(source, SourceInfo), type(source)

    targets_map = get_targets(project)
    if name in targets_map:
        raise TargetAlreadyExistsError(name, project, targets_map[name])

    target = Target(name, project, data, source)
    targets_map[name] = target
    return target


class TargetFactoryProtocol(Protocol, Generic[T]):
    def __call__(
        self,
        *,
        name: str = "",
        dependencies: Sequence[str | Address] = (),
        _stackframe: inspect.FrameInfo | None = None,
        _stackdepth: int = 0,
        **kwargs: Any,
    ) -> Target[T]:
        ...


def make_target_factory(
    func_name: str, default_name: str | None, dataclass_type: type[T_DataclassInstance]
) -> TargetFactoryProtocol[T_DataclassInstance]:
    """
    Creates a factory for creating targets of the given *dataclass_type*.

    If a *default_name* is specified, then the factory function may be called without a *name* parameter.
    Otherwise, the *name* is always required when calling the factory.
    """

    dataclass_fields = {field.name: TypeHint(field.type) for field in fields(dataclass_type)}

    def target_factory(
        name: str | None = default_name,
        dependencies: Sequence[str | Address] = (),
        _stackframe: inspect.FrameInfo | None = None,
        _stackdepth: int = 0,
        **kwargs: Any,
    ) -> Target[T_DataclassInstance]:
        project = Project.current()
        if _stackframe is None:
            _stackframe = inspect.stack()[_stackdepth + 1]

        if name is None:
            raise ValueError(f"{func_name}() missing 1 required argument: 'name'")

        # Modify some input parameters so that we can define a dataclass to have a `tuple` field, but the
        # factory accepts sequences.
        for key, value in kwargs.items():
            field_type = dataclass_fields.get(key)
            if isinstance(field_type, ClassTypeHint) and issubclass(field_type.type, tuple):
                kwargs[key] = tuple(value)
            elif isinstance(field_type, ClassTypeHint) and issubclass(field_type.type, Path):
                kwargs[key] = Path(value)

        target = create_target(name, project, dataclass_type(**kwargs), _stackframe)
        target.dependencies = [project.address.concat(Address(dep)).normalize() for dep in dependencies]
        return target

    target_factory.__name__ = func_name
    target_factory.__qualname__ = func_name
    return target_factory
