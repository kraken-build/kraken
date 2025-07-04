from __future__ import annotations

import http.server
import logging
import subprocess as sp
import tempfile
import typing as t
import webbrowser
from pathlib import Path
from typing import overload

logger = logging.getLogger(__name__)


class GraphvizWriter:
    """A helper class to write Dotviz files."""

    def __init__(self, out: t.TextIO, indent: str = "\t") -> None:
        """
        :param out: The output file to write to.
        :param indent: The string to use for every level of indentation.
        """

        self._out = out
        self._indent = indent
        self._level = 0
        self._edge_type: list[str] = []

    @property
    def _line_prefix(self) -> str:
        return self._level * self._indent

    def _escape(self, name: str) -> str:
        # TODO (@NiklasRosenstein): Improve escaping logic.
        if "\n" in name:
            raise ValueError("Cannot have newline (contained in {name!r})")
        chars = " ,.:#$/&"
        if any(c in name for c in chars):
            name = f'"{name}"'
        return name

    def _write_attrs(self, attrs: dict[str, str | None]) -> None:
        safe_attrs = {key: value for key, value in attrs.items() if value is not None}
        if safe_attrs:
            self._out.write("[")
            self._out.write(" ".join(f"{self._escape(key)}={self._escape(value)}" for key, value in safe_attrs.items()))
            self._out.write("]")

    def _write_scope(self, keyword: str, name: str | None, attrs: dict[str, str | None]) -> None:
        self._out.write(f"{self._line_prefix}{keyword} ")
        if name is not None:
            self._out.write(self._escape(name) + " ")
        self._out.write("{\n")
        self._level += 1
        for key, value in attrs.items():
            if value is not None:
                self._out.write(f"{self._line_prefix}{self._escape(key)}={self._escape(value)};\n")

    def graph(self, name: str | None = None, **attrs: str | None) -> None:
        """Open a `graph{}` block. Close it by calling :meth:`end`."""
        self._write_scope("graph", name, attrs)
        self._edge_type.append("--")

    def digraph(self, name: str | None = None, **attrs: str | None) -> None:
        """Open a `digraph{}` block. Close it by calling :meth:`end`."""
        self._write_scope("digraph", name, attrs)
        self._edge_type.append("->")

    def subgraph(self, name: str | None = None, **attrs: str | None) -> None:
        """Open a `subgraph{}` block. Close it by calling :meth:`end`."""
        self._write_scope("subgraph", name, attrs)
        self._edge_type.append(self._edge_type[-1])

    def end(self) -> None:
        """Close a previously opened block. Raises an :class:`AssertionError` if called too many times."""
        assert self._level >= 1, "called end() too many times"
        self._level -= 1
        self._edge_type.pop()
        self._out.write(self._line_prefix + "}\n")

    def set_node_style(self, **attrs: str | None) -> None:
        """Sets the node style in the current block."""
        self._out.write(self._line_prefix + "node ")
        self._write_attrs(attrs)
        self._out.write(";\n")

    def node(self, node_id: str, **attrs: str | None) -> None:
        """Draw a node in the current context."""
        self._out.write(self._line_prefix + self._escape(node_id))
        if attrs:
            self._write_attrs(attrs)
        self._out.write(";\n")

    def edge(self, source: str | t.Sequence[str], target: str | t.Sequence[str], **attrs: str | None) -> None:
        """Draw one or multiple edges in the current context from source to target. Specifying multiple
        nodes on either side will generate the cross product of edges between all nodes."""
        if isinstance(source, str):
            source = [source]
        if isinstance(target, str):
            target = [target]

        if not source or not target:
            raise ValueError("edge needs at least one source and at least one target")

        def _write_nodes(nodes: t.Sequence[str]) -> None:
            if len(nodes) == 1:
                self._out.write(self._escape(nodes[0]))
            else:
                self._out.write("{")
                self._out.write(" ".join(self._escape(node_id) for node_id in nodes))
                self._out.write("}")

        # TODO (@NiklasRosenstein): Does GraphViz support a syntax for multiple nodes on the left?
        for node_id in source:
            self._out.write(self._line_prefix)
            _write_nodes([node_id])
            self._out.write(f" {self._edge_type[-1]} ")
            _write_nodes(target)
            self._write_attrs(attrs)
            self._out.write(";\n")


@overload
def render(graphviz_code: str, format: str, algorithm: str = ...) -> bytes:
    """Renders the *graphviz_code* to an image file of the specified *format*. The default format is `"dot"`."""


@overload
def render(graphviz_code: str, format: str, algorithm: str = ..., *, output_file: Path) -> None:
    """Renders the *graphviz_code* to a file."""


def render(graphviz_code: str, format: str, algorithm: str = "dot", *, output_file: Path | None = None) -> None | bytes:
    command = [algorithm, f"-T{format}"]
    if output_file is not None:
        command += ["-o", str(output_file)]
    try:
        process = sp.run(command, input=graphviz_code.encode(), check=True, capture_output=True)
    except sp.CalledProcessError as exc:
        logger.error("%s: %s", exc, exc.stderr.decode())
        raise
    return process.stdout


def render_to_browser(graphviz_code: str, algorithm: str = "dot") -> None:
    """Renders the *graphviz_code* to an SVG file and opens it in the webbrowser. Blocks until the
    browser opened the page."""

    with tempfile.TemporaryDirectory() as tempdir:
        svg_file = Path(tempdir) / "graph.svg"
        render(graphviz_code, "svg", algorithm, output_file=svg_file)
        server = http.server.HTTPServer(
            ("", 0),
            lambda *args: http.server.SimpleHTTPRequestHandler(*args, directory=tempdir),
        )
        webbrowser.open(f"http://localhost:{server.server_port}/graph.svg")
        server.handle_request()
