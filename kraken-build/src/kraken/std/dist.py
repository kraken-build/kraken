"""Create distributions (archives) from build artifacts and resources."""

from __future__ import annotations

import abc
import logging
import tarfile
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Literal, Union, cast

import databind.json

from kraken.common import colored
from kraken.core import Project, Property, Task, TaskSet
from kraken.core.address import Address

from .descriptors.resource import BinaryArtifact, LibraryArtifact, Resource

logger = logging.getLogger(__name__)


@dataclass
class IndividualDistOptions:
    arcname: str | None = None
    exclude: Sequence[str] = ()
    include: Sequence[str] | None = None


@dataclass
class ConfiguredResource(Resource):
    options: IndividualDistOptions


class DistributionTask(Task):
    """Create an archive from a set of files and resources."""

    #: The output filename. If a string is specified, that string is treated relative
    #: to the project output directory. A Path object is treated relative to the project
    #: directory. Unless the :attr:`archive_type` property is set, the suffix will determine
    #: the type of archive that is created.
    output_file: Property[Path]

    #: The type of archive that will be created. Can be zip, tgz and tar.
    archive_type: Property[str]

    #: Prefix to add to all files added to the distribution.
    prefix: Property[str]

    #: A list of resources to include.
    resources: Property[list[ConfiguredResource]] = Property.default_factory(list)

    #: A resource that describes the output file.
    _output_file_resource: Property[Resource] = Property.output()

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self._output_file_resource.set(self.output_file.map(lambda p: Resource("dist", p)))

    # Task

    def execute(self) -> None:
        output_file = self.output_file.get()
        archive_type = self.archive_type.get_or(None)
        if archive_type is None:
            archive_type = output_file.suffix.lstrip(".")
            archive_type = {"tgz": "tar.gz", "txz": "tar.xz", "tbz2": "tar.bz2"}.get(archive_type, archive_type)
        assert isinstance(archive_type, str)

        print("Writing archive", colored(str(output_file), "yellow"))
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with wopen_archive(output_file, archive_type) as archive:
            for resource in self.resources.get():
                arcname = resource.options.arcname
                if arcname is None:
                    arcname = str(resource.path.relative_to(self.project.directory))
                print(
                    "  +",
                    colored(arcname or ".", "green"),
                    f"({resource.path})" if arcname != str(resource.path) else "",
                )
                add_to_archive(
                    archive,
                    arcname,
                    self.project.directory / resource.path,
                    resource.path,
                    resource.options.exclude,
                    resource.options.include,
                )


def wopen_archive(path: Path, type_: str) -> ArchiveWriter:
    """Open an archive at *path* for writing. The *type_* indicates what type of archive will be created.
    Accepted values for *type_* are `zip`, `tar`, `tar.gz`, `tar.bz2` and `tar.xz`."""

    if type_.startswith("tar."):
        return TarArchiveWriter(path, cast(Any, type_.partition(".")[-1]))
    elif type_ == "tar":
        return TarArchiveWriter(path, "")
    elif type_ == "zip":
        return ZipArchiveWriter(path)
    else:
        raise ValueError(f"unsupported archive type: {type_!r}")


def add_to_archive(
    writer: ArchiveWriter,
    arcname: str,
    path: Path,
    test_path: Path | None = None,
    exclude: Sequence[str] = (),
    include: Sequence[str] | None = None,
) -> None:
    """Recursively adds *path* to the archive *writer* under consideration of the *exclude* and *include* glob
    patterns that are tested against *test_path*.

    The glob patterns for the *exclude* and *include* arguments are tested against the full relative *test_path*
    as well as the individual filename. (NOTE(niklas.rosenstein): To support full .gitignore like behaviour, we'd
    need to test the entire range from name to full path).

    :param writer: The archive writer implementation.
    :param arcname: The name to give *path*. Sub-paths are appended to this name as normal.
    :param path: The path to write to the archive.
    :param test_path: The path to test the exclude/include patterns against. Sub-paths are appended to this as normal.
        Defaults to *path*.
    :param exclude: A sequence of glob patterns that, if matching, cause an element (file or directory) to be excluded.
    :param include: If specified, must be a sequence of glob patterns that will cause a file or directory to only be
        added if any pattern matches, and no *exclude* pattern matches.
    """

    test_path = test_path or path
    s_test_path = str(test_path)

    if any(fnmatch(s_test_path, x) or fnmatch(test_path.name, x) for x in exclude):
        return
    if include is not None and not any(fnmatch(s_test_path, x) or fnmatch(test_path.name, x) for x in include):
        return

    if path.is_dir():
        for item in path.iterdir():
            add_to_archive(writer, arcname + "/" + item.name, item, test_path / item.name, exclude, include)
    else:
        writer.add_file(arcname, path)


class ArchiveWriter(abc.ABC):
    """Base class to write an archive file."""

    @abc.abstractmethod
    def add_file(self, arcname: str, path: Path) -> None:
        """Add a file to the archive."""

    @abc.abstractmethod
    def close(self) -> None:
        pass

    def add_path(self, arcname: str, path: Path) -> None:
        """Recursively add the contents of all files under *path*."""

        if path.is_dir():
            for item in path.iterdir():
                self.add_path(arcname + "/" + item.name, item)
        else:
            self.add_file(arcname, path)

    def __enter__(self) -> ArchiveWriter:
        return self

    def __exit__(self, *a: Any) -> None:
        self.close()


class TarArchiveWriter(ArchiveWriter):
    def __init__(self, path: Path, type_: Literal["", "gz", "bz2", "xz"]) -> None:
        self._archive = tarfile.open(path, mode="w:" + type_)  # type: ignore[call-overload]

    def close(self) -> None:
        self._archive.close()

    def add_file(self, arcname: str, path: Path) -> None:
        self._archive.add(path, arcname, recursive=False)


class ZipArchiveWriter(ArchiveWriter):
    def __init__(self, path: Path) -> None:
        self._archive = zipfile.ZipFile(path, "w")

    def close(self) -> None:
        self._archive.close()

    def add_file(self, arcname: str, path: Path) -> None:
        self._archive.write(path, arcname)


def dist(
    *,
    name: str,
    dependencies: Sequence[str | Address | Task] | Mapping[str | Address, Mapping[str, Any] | IndividualDistOptions],
    output_file: str | Path,
    archive_type: str | None = None,
    prefix: str | None = None,
    project: Project | None = None,
) -> DistributionTask:
    """Create a task that produces a distribution from the resources provided by the tasks specified with *include*.

    :param name: The name of the task.
    :param dependencies: A list of tasks or task selectors (resolved relative to the *project*) that provide the
        resources that should be included in the generated archive. If a dictionary is specified, instead, it must
        map each dependency to a dictionary of settings that can be deserialized into :class:`IndividualDistOptions`.
    :param output_file: The output filename to write to. If a string is specified, it will be treated relative to the
        project build directory. If a path object is specified, it will be treated relative to the project directory.
    :param archive_type: The type of archive to create (e.g. `zip`, `tar`, `tar.gz`, `tar.bz2` or `tar.xz`). If left
        empty, the archive type is derived from the *output_filename* suffix.
    :param project: The project to create the task for.
    """

    project = project or Project.current()

    if isinstance(output_file, str):
        output_file = project.build_directory / output_file
    else:
        output_file = project.directory / output_file

    if isinstance(dependencies, Sequence):
        dependencies = cast(
            Mapping[str | Address, Union[Mapping[str, Any], IndividualDistOptions]], {d: {} for d in dependencies}
        )
    dependencies_map = {
        k: databind.json.load(v, IndividualDistOptions) if not isinstance(v, IndividualDistOptions) else v
        for k, v in dependencies.items()
    }
    dependencies_set = TaskSet.build(project, dependencies_map)

    # This associates the IndividualDistOptions specified in *dependencies* to the Resource(s)
    # provided by the task(s).
    resources = (
        dependencies_set.select(Resource)
        .dict_supplier()
        .map(
            lambda resources: get_configured_resources(
                resources,
                {str(k): v for k, v in dependencies_map.items()},
                dependencies_set,
            )
        )
    )

    dist_task = project.task(name, DistributionTask)
    dist_task.resources = resources
    dist_task.output_file = output_file
    dist_task.archive_type = archive_type
    dist_task.prefix = prefix
    return dist_task


def get_configured_resources(
    resources: dict[Task, list[Resource]],
    dependencies_map: dict[str, IndividualDistOptions],
    dependencies_set: TaskSet,
) -> list[ConfiguredResource]:
    configured_resources = []

    for task, task_resources in resources.items():
        for resource in task_resources:
            task_options = dependencies_map[next(iter(dependencies_set.partitions()[task]))]
            options = IndividualDistOptions(**vars(task_options))

            if options.arcname is None and isinstance(resource, (BinaryArtifact, LibraryArtifact)):
                options.arcname = resource.name
            configured_resources.append(ConfiguredResource(**vars(resource), options=options))
    return configured_resources
