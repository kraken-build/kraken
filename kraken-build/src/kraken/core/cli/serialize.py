from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from pathlib import Path

import dill  # type: ignore[import-untyped]

from kraken.common import pluralize
from kraken.core import Context, TaskGraph

logger = logging.getLogger(__name__)
state_file_regex = r"^state-.*\.dill$"
state_file_template = "state-{name}.dill"


def load_build_state(state_dirs: Iterable[Path]) -> tuple[Context, TaskGraph] | tuple[None, None]:
    # Find all state files that match the state filename format.
    state_files = []
    for state_dir in state_dirs:
        if state_dir.is_dir():
            for path in state_dir.iterdir():
                if re.match(state_file_regex, path.name):
                    state_files.append(path)
    if not state_files:
        return None, None

    logger.info(
        "Resuming from %d build %s (%s)",
        len(state_files),
        pluralize("state", state_files),
        ", ".join(file.name for file in state_files),
    )

    context: Context | None = None
    graph: TaskGraph | None = None

    for state_file in sorted(state_files):
        with state_file.open("rb") as fp:
            new_graph: TaskGraph = dill.load(fp)
        if context is None or graph is None:
            # We want to retrieve the entire, original build graph.
            context, graph = new_graph.context, new_graph.root
        # Take the results from the final graph (only this graph contains results).
        graph.results_from(new_graph)

    assert context is not None and graph is not None
    return context, graph


def save_build_state(state_dir: Path, name: str, graph: TaskGraph) -> None:
    state_file = state_dir / state_file_template.format(name=name)
    state_dir.mkdir(parents=True, exist_ok=True)
    with state_file.open("wb") as fp:
        dill.dump(graph, fp)
    for file in state_dir.iterdir():
        if file != state_file:
            file.unlink()
    logger.info('Saving build state to "%s"', state_file)
