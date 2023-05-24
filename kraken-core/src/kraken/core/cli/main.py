from __future__ import annotations

import argparse
import builtins
import contextlib
import io
import json
import logging
import os
import pdb
import sys
import textwrap
from functools import partial
from pathlib import Path
from typing import Any, NoReturn
import pretty_errors

from kraken.common import (
    BuildscriptMetadata,
    CurrentDirectoryProjectFinder,
    LoggingOptions,
    RequirementSpec,
    appending_to_sys_path,
    deprecated_get_requirement_spec_from_file_header,
    get_terminal_width,
    not_none,
    propagate_argparse_formatter_to_subparser,
)
from kraken.common.pyenv import get_distributions
from nr.io.graphviz.render import render_to_browser
from nr.io.graphviz.writer import GraphvizWriter
from termcolor import colored

from kraken.core import __version__
from kraken.core.address import Address
from kraken.core.cli import serialize
from kraken.core.cli.executor import ColoredDefaultPrintingExecutorObserver, status_to_text
from kraken.core.cli.option_sets import BuildOptions, GraphOptions, RunOptions, VizOptions
from kraken.core.system.context import Context
from kraken.core.system.errors import BuildError, ProjectNotFoundError
from kraken.core.system.graph import TaskGraph
from kraken.core.system.project import Project
from kraken.core.system.property import Property
from kraken.core.system.task import GroupTask, Task


pretty_errors.configure(
    separator_character  = pretty_errors.CYAN + '≈',
    filename_display     = pretty_errors.FILENAME_COMPACT,
    line_number_first    = False,
    lines_before         = 2,
    lines_after          = 2,
    display_link         = True,
    display_locals       = False,
    display_arrow        = True,
    display_trace_locals = False,
    display_timestamp    = False,
    prefix               = pretty_errors.MAGENTA + '\nLet no joyful voice be heard! Let no man look up at the sky with hope! And let this day be cursed by we who ready to wake... the Kraken!' + pretty_errors.default_config.line_color + '\nAlas sailor, there is nought you can do. Please check your Kraken build script, and then report this stacktrace to the Kraken repository:\n' + pretty_errors.CYAN + 'https://github.com/kraken-build/kraken-build/issues\n\n' + pretty_errors.MAGENTA + '> ' + pretty_errors.default_config.line_color + 'Kraken Version: ' + pretty_errors.BRIGHT_MAGENTA + __version__ + pretty_errors.MAGENTA + '\n>',
    infix                = pretty_errors.MAGENTA + '> ',
    arrow_head_character = '»',
    arrow_tail_character = '«',
    trace_lines_before   = 0,
    trace_lines_after    = 0,
    header_color         = pretty_errors.default_config.line_color,
    line_color           = pretty_errors.MAGENTA + '> ' + pretty_errors.default_config.line_color,
    link_color           = pretty_errors.CYAN + '> ' + pretty_errors.default_config.line_color,
    code_color           = pretty_errors.CYAN + '> ' + pretty_errors.default_config.line_color,
    line_number_color    = pretty_errors.MAGENTA + '#' + pretty_errors.default_config.line_color,
    filename_color       = pretty_errors.MAGENTA + '> ' + pretty_errors.default_config.line_color,
    exception_color      = pretty_errors.CYAN + '> ' + pretty_errors.YELLOW,
    exception_arg_color  = pretty_errors.MAGENTA + '> ' + pretty_errors.YELLOW,
    exception_file_color = pretty_errors.MAGENTA + '> ' + pretty_errors.YELLOW,
    function_color       = pretty_errors.CYAN,
    local_name_color     = pretty_errors.CYAN + '> ' + pretty_errors.default_config.line_color,
    local_value_color    = pretty_errors.YELLOW,
    inner_exception_message = pretty_errors.MAGENTA + '\n> ' + pretty_errors.default_config.line_color + "During handling of the above exception, another exception occurred:\n",
    syntax_error_color = pretty_errors.MAGENTA,
    )

if not pretty_errors.terminal_is_interactive:
    pretty_errors.mono()


BUILD_SCRIPT = Path(".kraken.py")
BUILD_SUPPORT_DIRECTORY = "build-support"
logger = logging.getLogger(__name__)
print = partial(builtins.print, flush=True)


def _get_argument_parser(prog: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog,
        formatter_class=lambda prog: argparse.RawDescriptionHelpFormatter(prog, width=120, max_help_position=60),
        description=textwrap.dedent(
            """
            The Kraken build system.

            Kraken focuses on ease of use and simplicity to model complex task orchestration workflows.
            """
        ),
    )
    subparsers = parser.add_subparsers(dest="cmd")

    run = subparsers.add_parser(
        "run",
        aliases=["r"],
        # The following makes sure --all will not be considered as an abbreviation of --allow-whatever
        # This is important because we do want to warn in case the user specifies the (invalid) --all flag
        # See https://docs.python.org/dev/library/argparse.html#allow-abbrev
        allow_abbrev=False,
    )
    LoggingOptions.add_to_parser(run)
    BuildOptions.add_to_parser(run)
    GraphOptions.add_to_parser(run, include_all_option=False)
    RunOptions.add_to_parser(run)

    query = subparsers.add_parser("query", aliases=["q"])
    query_subparsers = query.add_subparsers(dest="query_cmd")

    ls = query_subparsers.add_parser("ls", description="list all tasks and task groups in the build")
    LoggingOptions.add_to_parser(ls)
    BuildOptions.add_to_parser(ls)
    GraphOptions.add_to_parser(ls, saveable=False)

    describe = query_subparsers.add_parser(
        "describe",
        aliases=["d"],
        description="describe one or more tasks in detail",
    )
    LoggingOptions.add_to_parser(describe)
    BuildOptions.add_to_parser(describe)
    GraphOptions.add_to_parser(describe, saveable=False)

    viz = query_subparsers.add_parser("visualize", aliases=["viz", "v"], description="generate a GraphViz of the build")
    LoggingOptions.add_to_parser(viz)
    BuildOptions.add_to_parser(viz)
    GraphOptions.add_to_parser(viz, saveable=False)
    VizOptions.add_to_parser(viz)

    tree = query_subparsers.add_parser("tree", aliases=["t"], description="Output the project and task tree.")
    LoggingOptions.add_to_parser(tree)
    BuildOptions.add_to_parser(tree)
    GraphOptions.add_to_parser(tree)

    # This command is used by kraken-wrapper to produce a lock file.
    env = query_subparsers.add_parser("env", description="produce a JSON file of the Python environment distributions")
    LoggingOptions.add_to_parser(env)

    propagate_argparse_formatter_to_subparser(parser)
    return parser


def _load_build_state(
    exit_stack: contextlib.ExitStack,
    build_options: BuildOptions,
    graph_options: GraphOptions,
) -> tuple[Context, TaskGraph]:
    """
    This function loads the build state for the current working directory; which involves either executing the
    Kraken build script or loading one or more state files from their serialized form on disk.
    """

    if graph_options.restart and not graph_options.resume:
        raise ValueError("the --restart option requires the --resume flag")

    # Calculate the main subproject based on the project directory.
    root_directory = build_options.project_dir.absolute().resolve()
    try:
        subproject_directory = Path.cwd().relative_to(root_directory)
    except ValueError:
        raise ValueError(
            f"-p,--project-dir must be a parent directory of {Path.cwd()}, not a sibling/subdirectory "
            f"(got: {build_options.project_dir})"
        )

    # For consistency, we always act as if Kraken was run from the project root directory.
    # Using the `subproject_directory`, we later fitler down which tasks are selected / how relative
    # task references on the CLI are resolved.
    os.chdir(root_directory)

    project_info = CurrentDirectoryProjectFinder.default().find_project(Path.cwd())
    if not project_info:
        # We are OKAY with resuming a build from serialized state files even if no build script exists in the
        # current working directory; this is a feature that is often useful for debugging purposes when you want
        # to inspect the final state of a build, like from CI.
        if not graph_options.resume:
            raise ValueError(f'no Kraken build script found in the directory "{build_options.project_dir}"')

    # Before we can deserialize the build state, we must add the additional paths to `sys.path` that are defined
    # in by the script using the buildscript() function, or for backwards compatibility, in the file header as
    # comments.

    # Note that if we are simply going to execute the build script (i.e. not deserializing from state files),
    # we can rely on the buildscript() call in the script to update `sys.path`; but if the deprecated file header
    # is used to define the pythonpath we still need to parse it explicitly.

    if project_info:
        # Attempt to read the requirement spec in the deprecated format first.
        requirements = deprecated_get_requirement_spec_from_file_header(project_info.script)

        # If the file does not have the deprecated requirement spec file header as comments, we instead want
        # to capture the buildscript() call by tenatively executing the script. However, we only need to do
        # this if we want to resume from a serialized build state. When we need to execute the full script
        # anyway, we can rely on a callback that we register for when buildscript() is called to update
        # the `sys.path`, which avoids that we execute the script twice.
        if not requirements and graph_options.resume and project_info.runner.has_buildscript_call(project_info.script):
            with BuildscriptMetadata.capture() as future:
                project_info.runner.execute_script(project_info.script, {})
            assert future.done()
            requirements = RequirementSpec.from_metadata(future.result())

        # Update `sys.path` with the python path from the requirement spec, if any.
        if requirements:
            exit_stack.enter_context(appending_to_sys_path(requirements.pythonpath))

    context: Context | None = None

    # Deserialize the build state from files in the build state directory (+ extra dirs) if that is what
    # the user requested.
    if graph_options.resume:
        context, graph = serialize.load_build_state([build_options.state_dir] + build_options.additional_state_dirs)
        if not graph:
            raise ValueError("cannot --resume without build state")
        if graph and graph_options.restart:
            graph.restart()
        assert context is not None

    # Otherwise, we need to execute the build script.
    else:
        if build_options.no_load_project:
            raise ValueError(
                "no existing build state was loaded; typically that would load the root project "
                "but --no-load-project was specified."
            )

        # Register a callback for when the buildscript calls the buildscript() method. Any requirements passed
        # to the function are already expected to have been handled with by the Kraken wrapper, but we need to
        # handle the additions to `sys.path` here.
        def _buildscript_metadata_callback(metadata: BuildscriptMetadata) -> None:
            requirements = RequirementSpec.from_metadata(metadata)
            exit_stack.enter_context(appending_to_sys_path(requirements.pythonpath))

        context = Context(build_options.build_dir)

        with BuildscriptMetadata.callback(_buildscript_metadata_callback):
            context.load_project(Path.cwd())
            context.finalize()
            graph = TaskGraph(context)

    assert graph is not None

    # Serialize the build graph, even on failure, at the end of the build.
    if not graph_options.no_save:
        exit_stack.callback(
            lambda: serialize.save_build_state(build_options.state_dir, build_options.state_name, not_none(graph))
        )

    # Find the project from which we'll resolve relative task references based on the original current working
    # directory relative to the project root directory.
    relative_address = Address(":" + ":".join(subproject_directory.parts))

    # Find the project that contains the current working directory.
    try:
        context.focus_project = context.get_project(relative_address)
        logger.info("project '%s' is the main project", context.focus_project.address)
    except ProjectNotFoundError as e:
        logger.info("project '%s' does not exist, setting context.focus_project = None", e.address)
        context.focus_project = None

    # Deselect all tasks.
    for task in graph.root.tasks():
        task.selected = False

    # Mark tasks that were explicitly selected on the command-line as such. Tasks may alter their behaviour
    # based on whether they were explicitly selected or not.
    if graph_options.tasks:
        selected = context.resolve_tasks(graph_options.tasks, relative_to=relative_address, set_selected=True)
        targets = selected
    else:
        targets = context.resolve_tasks(None, relative_to=relative_address)

    # Trim the graph down to the selected or default tasks.
    if not graph_options.all:
        graph = graph.trim(targets)

    return context, graph


def run(
    exit_stack: contextlib.ExitStack,
    build_options: BuildOptions,
    graph_options: GraphOptions,
    run_options: RunOptions,
) -> None:
    context, graph = _load_build_state(
        exit_stack=exit_stack,
        build_options=build_options,
        graph_options=graph_options,
    )

    context.observer = ColoredDefaultPrintingExecutorObserver(
        context.resolve_tasks(run_options.exclude_tasks or []),
        context.resolve_tasks(run_options.exclude_tasks_subgraph or []),
    )

    if run_options.skip_build:
        print("note: skipped build due to -s,--skip-build option.")
        sys.exit(0)
    else:
        if not graph:
            if run_options.allow_no_tasks:
                print("note: no tasks were selected (--allow-no-tasks)", "blue", file=sys.stderr)
                sys.exit(0)
            else:
                print("error: no tasks were selected", file=sys.stderr)
                sys.exit(1)

        try:
            context.execute(graph)
        except BuildError as exc:
            print()
            print("error:", exc, file=sys.stderr)
            sys.exit(1)


def ls(graph: TaskGraph) -> None:
    goal_tasks = set(graph.tasks(goals=True))
    all_tasks = set(graph.tasks())
    if not all_tasks:
        print("no tasks")
        sys.exit(1)
    longest_name = max(map(len, (t.path for t in all_tasks))) + 1

    print()
    print(colored("Tasks", "blue", attrs=["bold", "underline"]))
    print()

    width = get_terminal_width(120)

    def _print_task(task: Task) -> None:
        line = [task.path.ljust(longest_name)]
        remaining_width = width - len(line[0])
        if task in goal_tasks:
            line[0] = colored(line[0], "green")
        if task.default:
            line[0] = colored(line[0], attrs=["bold"])
        status = graph.get_status(task)
        if status is not None:
            line.append(f"[{status_to_text(status)}]")
            status_length = 2 + len(status_to_text(status, colored=False)) + 1
            remaining_width -= status_length
        description = task.get_description()
        if description:
            remaining_width -= 2
            if remaining_width <= 0:
                remaining_width = width
            for part in textwrap.wrap(
                description,
                remaining_width,
                subsequent_indent=(width - remaining_width) * " ",
            ):
                line.append(part)
                line.append("\n")
            line.pop()
        print("  " + " ".join(line))

    def sort_key(task: Task) -> str:
        return task.path

    for task in sorted(graph.tasks(), key=sort_key):
        if isinstance(task, GroupTask):
            continue
        _print_task(task)

    print()
    print(colored("Groups", "blue", attrs=["bold", "underline"]))
    print()

    for task in sorted(graph.tasks(), key=sort_key):
        if not isinstance(task, GroupTask):
            continue
        _print_task(task)

    print()


def tree(graph: TaskGraph) -> None:
    tasks = set(graph.tasks())

    # Filter out empty group tasks.
    tasks = {t for t in tasks if not isinstance(t, GroupTask) or t.tasks}

    # Find the projects we'd be looking to output.
    projects = {x.project for x in tasks}
    if graph.context.focus_project:
        projects.add(graph.context.focus_project)

    # Make sure we include all projects in between.
    for p in list(projects):
        while p and p.parent:
            p = p.parent
            projects.add(p)

    def _format_address(obj: Project | Task) -> str:
        address = obj.address

        parent = address.parent.set_container(True) if address and not address.is_root() else None
        if parent:
            result = colored(str(parent), "grey")
        else:
            result = ""
        result = result + colored(":" if address.is_root() else address.name, attrs=["bold"])

        if isinstance(obj, Project):
            if address.is_root():
                result += colored(" (root project)", "green")
            else:
                result += colored(" (sub project)", "green")
        if obj == graph.context.focus_project:
            result += colored(" (focus)", "cyan")
        if isinstance(obj, GroupTask):
            if obj.default:
                result += colored(" (default group)", "yellow", attrs=["bold"])
            else:
                result += colored(" (group)", "yellow")
        elif isinstance(obj, Task):
            if obj.default:
                result += colored(" (default task)", "blue", attrs=["bold"])
            else:
                result += colored(" (task)", "blue")
        if isinstance(obj, Task):
            if obj.selected:
                result += colored(" (selected)", "magenta")

        return result

    def _recurse(obj: Project | Task, prefix: str, is_last: bool) -> None:
        if not (isinstance(obj, Project) and obj.address.is_root()):
            if is_last:
                this_prefix = prefix + "└── "
                child_prefix = prefix + "    "
            else:
                this_prefix = prefix + "├── "
                child_prefix = prefix + "│   "
        else:
            this_prefix = child_prefix = ""
        if isinstance(obj, Project):
            print(f"{colored(this_prefix, 'grey')}{_format_address(obj)}")
            members = sorted(list(obj.tasks().values()) + list(obj.subprojects().values()), key=lambda x: x.name)
            # Don't show empty groups
            members = [m for m in members if not isinstance(m, GroupTask) or m.tasks]
            # Don't show tasks/projects that are not in the graph.
            members = [m for m in members if m in tasks or m in projects]
            for idx, member in enumerate(members):
                is_last = idx == len(members) - 1
                _recurse(member, child_prefix, is_last)
        else:
            print(f"{colored(this_prefix, 'grey')}{_format_address(obj)}")

    print()
    _recurse(graph.context.root_project, "", True)


def describe(graph: TaskGraph) -> None:
    """
    Describes the selected tasks.
    """

    tasks = [t for t in graph.tasks() if t.selected]
    print("selected", len(tasks), "task(s)")
    print()

    for task in tasks:
        print("Group" if isinstance(task, GroupTask) else "Task", colored(task.path, attrs=["bold", "underline"]))
        print("  Type:", type(task).__module__ + "." + type(task).__name__)
        print("  Type defined in:", colored(sys.modules[type(task).__module__].__file__ or "???", "cyan"))
        print("  Default:", task.default)
        print("  Selected:", task.selected)
        print("  Capture:", task.capture)
        rels = list(task.get_relationships())
        print(colored("  Relationships", attrs=["bold"]), f"({len(rels)})")
        for rel in rels:
            print(
                "".ljust(4),
                colored(rel.other_task.path, "blue"),
                f"before={rel.inverse}, strict={rel.strict}",
            )
        print("  " + colored("Properties", attrs=["bold"]) + f" ({len(type(task).__schema__)})")
        longest_property_name = max(map(len, type(task).__schema__.keys())) if type(task).__schema__ else 0
        for key in type(task).__schema__:
            prop: Property[Any] = getattr(task, key)
            print(
                "".ljust(4),
                (key + ":").ljust(longest_property_name + 1),
                f'{colored(prop.get_or("<unset>"), "blue")}',
            )
        print()


def visualize(graph: TaskGraph, viz_options: VizOptions) -> None:
    root = graph.root
    if viz_options.reduce or viz_options.reduce_keep_explicit:
        root = root.reduce(keep_explicit=viz_options.reduce_keep_explicit)
        graph = graph.reduce(keep_explicit=viz_options.reduce_keep_explicit)

    buffer = io.StringIO()
    writer = GraphvizWriter(buffer if viz_options.show else sys.stdout)
    writer.digraph(fontname="monospace", rankdir="LR")
    writer.set_node_style(style="filled", shape="box")

    style_default = {"penwidth": "3"}
    style_goal = {"fillcolor": "lawngreen"}
    style_select = {"fillcolor": "darkgoldenrod1"}
    style_group = {"shape": "ellipse"}
    style_edge_non_strict = {"style": "dashed"}
    style_edge_implicit = {"color": "gray"}

    writer.subgraph("cluster_#legend", label="Legend")
    # writer.node("#task", label="task")
    writer.node("#group", label="group task", **style_group)
    writer.node("#default", label="runs by default", **style_default)
    writer.node("#selected", label="task will run", **style_select)
    writer.node("#goal", label="goal task", **style_goal)
    writer.end()

    writer.subgraph("cluster_#build", label="Build Graph")

    main = root if viz_options.inactive else graph
    goal_tasks = set(graph.tasks(goals=True))
    selected_tasks = set(graph.tasks())

    for task in main.tasks():
        style = {}
        style.update(style_default if task.default else {})
        style.update(style_group if isinstance(task, GroupTask) else {})
        style.update(style_select if task in selected_tasks else {})
        style.update(style_goal if task in goal_tasks else {})

        writer.node(task.path, **style)
        for predecessor in main.get_predecessors(task, ignore_groups=False):
            writer.edge(
                predecessor.path,
                task.path,
                **({} if main.get_edge(predecessor, task).strict else style_edge_non_strict),
                **(style_edge_implicit if main.get_edge(predecessor, task).implicit else {}),
            )

    writer.end()
    writer.end()

    if viz_options.show:
        render_to_browser(buffer.getvalue())


def env() -> None:
    dists = sorted(get_distributions().values(), key=lambda dist: dist.name)
    print(json.dumps([dist.to_json() for dist in dists], sort_keys=True))


def main_internal(prog: str, argv: list[str] | None, pdb_enabled: bool) -> NoReturn:
    parser = _get_argument_parser(prog)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if not args.cmd:
        parser.print_usage()
        sys.exit(0)

    if LoggingOptions.available(args):
        LoggingOptions.collect(args).init_logging()

    if pdb_enabled:
        logger.info("note: KRAKEN_PDB=1 is set, an interactive debugging session will be started on exit.")
        logger.info("note: Exceptions raised in tasks will not trigger an interactive debugging session.")

    if args.cmd in ("run", "r"):
        with contextlib.ExitStack() as exit_stack:
            run(exit_stack, BuildOptions.collect(args), GraphOptions.collect(args), RunOptions.collect(args))

    elif args.cmd in ("query", "q"):
        if not args.query_cmd:
            parser.print_usage()
            sys.exit(0)

        if args.query_cmd == "env":
            env()
            sys.exit(0)

        build_options = BuildOptions.collect(args)
        graph_options = GraphOptions.collect(args)

        with contextlib.ExitStack() as exit_stack:
            _context, graph = _load_build_state(
                exit_stack=exit_stack,
                build_options=build_options,
                graph_options=graph_options,
            )

            if args.query_cmd == "ls":
                ls(graph)
            elif args.query_cmd in ("describe", "d"):
                describe(graph)
            elif args.query_cmd in ("visualize", "viz", "v"):
                visualize(graph, VizOptions.collect(args))
            elif args.query_cmd in ("t", "tree"):
                tree(graph)
            else:
                assert False, args.query_cmd

    else:
        parser.print_usage()

    sys.exit(0)


def main(prog: str = "kraken", argv: list[str] | None = None) -> NoReturn:
    pdb_enabled = os.getenv("KRAKEN_PDB") == "1"
    profile_outfile = os.getenv("KRAKEN_PROFILING")
    try:
        if profile_outfile:
            import cProfile as profile

            with open(profile_outfile, "w"):  # Make sure the file exists
                pass

            prof = profile.Profile()
            try:
                prof.runcall(main_internal, prog, argv, pdb_enabled)
            finally:
                prof.dump_stats(profile_outfile)
        else:
            main_internal(prog, argv, pdb_enabled)
        sys.exit(0)
    except:  # noqa: E722
        if pdb_enabled:
            pdb.post_mortem()
        raise


if __name__ == "__main__":
    main()
