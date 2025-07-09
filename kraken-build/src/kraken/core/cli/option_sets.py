from __future__ import annotations

import dataclasses
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse

logger = logging.getLogger(__name__)
DEFAULT_BUILD_DIR = Path("build")
BUILD_STATE_DIR = ".kraken/buildenv"


@dataclasses.dataclass(frozen=True)
class BuildOptions:
    build_dir: Path
    project_dir: Path
    state_dir: Path
    additional_state_dirs: list[Path]
    no_load_project: bool
    state_name: str

    @staticmethod
    def add_to_parser(parser: argparse.ArgumentParser) -> None:
        group = parser.add_argument_group("build options")
        group.add_argument(
            "-b",
            "--build-dir",
            metavar="PATH",
            type=Path,
            default=DEFAULT_BUILD_DIR,
            help="the build directory to write to [default: %(default)s]",
        )
        group.add_argument(
            "-p",
            "--project-dir",
            metavar="PATH",
            type=Path,
            default=Path.cwd(),
            help="the root directory of the project. If this is specified, it should point to an existing directory "
            "that contains a build script and it must be the same or a parent of the current directory. When "
            "invoked with this option, task references are resolved relative to the Kraken project that is "
            "represented by the current working directory. (note: this option is automatically passed when using "
            "kraken-wrapper as it finds the respective project automatically).",
        )
        group.add_argument(
            "--state-name",
            metavar="NAME",
            help="specify a name for the generated state file; if not specified, a short random ID is used",
            default=str(uuid.uuid4())[:7],
        )
        group.add_argument(
            "--state-dir",
            metavar="PATH",
            type=Path,
            help=f"specify the main build state directory [default: ${{--build-dir}}/{BUILD_STATE_DIR}]",
        )
        group.add_argument(
            "--additional-state-dir",
            metavar="PATH",
            type=Path,
            help="specify an additional state directory to load build state from. can be specified multiple times",
        )
        group.add_argument(
            "--no-load-project",
            action="store_true",
            help="do not load the root project. this is only useful when loading an existing build state",
        )

    @classmethod
    def collect(cls, args: argparse.Namespace) -> BuildOptions:
        return cls(
            build_dir=args.build_dir,
            project_dir=args.project_dir,
            state_name=args.state_name,
            state_dir=args.state_dir or args.build_dir / BUILD_STATE_DIR,
            additional_state_dirs=args.additional_state_dir or [],
            no_load_project=args.no_load_project,
        )


@dataclasses.dataclass(frozen=True)
class GraphOptions:
    tasks: list[str] | None
    resume: bool
    restart: bool
    no_save: bool
    all: bool

    @staticmethod
    def add_to_parser(parser: argparse.ArgumentParser, saveable: bool = True) -> None:
        group = parser.add_argument_group("graph options")
        group.add_argument("--resume", action="store_true", help="deprecated since v0.45.0.")
        group.add_argument(
            "--restart",
            choices=("all",),
            help="load previous build state, but discard existing results (requires --resume)",
        )

        group.add_argument("--all", action="store_true", help="include all tasks in the build graph")

        # --all may make no sense
        # e.g. we don't want `kraken run --all` to be possible.
        # See https://github.com/kraken-build/kraken-core/pull/37#discussion_r1171300400
        group.add_argument(
            "tasks",
            metavar="task",
            nargs="*",
            help="one or more tasks to include in the build graph and mark as selected. if not set, default "
            "tasks are included in the build graph but not selected.",
            default=[],
        )

        if saveable:
            group.add_argument(
                "--save", action="store_true", help="deprecated since v0.45.0. the default is to not save."
            )
            group.add_argument("--no-save", action="store_true", help="deprecated since v0.45.0.")

    @classmethod
    def collect(cls, args: argparse.Namespace) -> GraphOptions:
        if args.save:
            logger.warning("the --save/--no-save options are deprecated since kraken v0.45.0")
        if args.resume:
            logger.warning("the --resume option is deprecated since kraken v0.45.0")
        if args.restart:
            logger.warning("the --restart option is deprecated since kraken v0.45.0")

        return cls(
            tasks=args.tasks or None,
            resume=args.resume,
            restart=args.restart,
            no_save=not args.save,
            all=getattr(args, "all", False),
        )


@dataclasses.dataclass(frozen=True)
class ExcludeOptions:
    exclude_tasks: list[str] | None
    exclude_tasks_subgraph: list[str] | None

    _group_name = "exclude options"

    @classmethod
    def add_to_parser(cls, parser: argparse.ArgumentParser) -> argparse._ArgumentGroup:
        group = parser.add_argument_group(cls._group_name)
        group.add_argument("-x", "--exclude", metavar="TASK", action="append", help="exclude one or more tasks")
        group.add_argument(
            "-X",
            "--exclude-subgraph",
            action="append",
            metavar="TASK",
            help="exclude the entire subgraphs of one or more tasks",
        )
        return group

    @classmethod
    def collect(cls, args: argparse.Namespace) -> ExcludeOptions:
        return cls(
            exclude_tasks=args.exclude or [],
            exclude_tasks_subgraph=args.exclude_subgraph or [],
        )


@dataclasses.dataclass(frozen=True)
class RunOptions(ExcludeOptions):
    allow_no_tasks: bool
    skip_build: bool

    _group_name = "run options"

    @classmethod
    def add_to_parser(cls, parser: argparse.ArgumentParser) -> argparse._ArgumentGroup:
        group = super().add_to_parser(parser)
        group.add_argument("-s", "--skip-build", action="store_true", help="just load the project, do not build")
        group.add_argument("-0", "--allow-no-tasks", action="store_true", help="don't error if no tasks got selected")
        return group

    @classmethod
    def collect(cls, args: argparse.Namespace) -> RunOptions:
        return cls(
            skip_build=args.skip_build,
            allow_no_tasks=args.allow_no_tasks,
            exclude_tasks=args.exclude or [],
            exclude_tasks_subgraph=args.exclude_subgraph or [],
        )


@dataclasses.dataclass(frozen=True)
class VizOptions:
    inactive: bool
    show: bool
    reduce: bool
    reduce_keep_explicit: bool

    @staticmethod
    def add_to_parser(parser: argparse.ArgumentParser) -> None:
        group = parser.add_argument_group("visualization options")
        group.add_argument("-i", "--inactive", action="store_true", help="include inactive tasks in the graph")
        group.add_argument("-s", "--show", action="store_true", help="show the graph in the browser (requires dot)")
        group.add_argument("-R", "--reduce", action="store_true", help="fully transitively reduce the graph")
        group.add_argument(
            "-r",
            "--reduce-keep-explicit",
            action="store_true",
            help="transitively reduce the graph but keep explicit edges",
        )

    @classmethod
    def collect(cls, args: argparse.Namespace) -> VizOptions:
        return cls(
            inactive=args.inactive,
            show=args.show,
            reduce=args.reduce,
            reduce_keep_explicit=args.reduce_keep_explicit,
        )
