from pathlib import Path

import pytest

from kraken.core import Context, Project


def test_import_current_context_and_project_from_kraken_build() -> None:
    """Test that you can import the current Kraken build context and project from `kraken.build`."""

    with pytest.raises(RuntimeError):
        from kraken.build import context

    with pytest.raises(RuntimeError):
        from kraken.build import project

    with Context(Path.cwd()).as_current() as ctx:
        with Project("test", Path.cwd(), None, ctx).as_current() as proj:
            from kraken.build import context, project  # noqa: F811

            assert context is ctx
            assert project is proj

        with Project("subproject", Path.cwd() / "subproject", None, ctx).as_current() as subproj:
            from kraken.build import context, project  # noqa: F811

            assert context is ctx
            assert project is subproj

        from kraken.build import context

        assert context is ctx

        with pytest.raises(RuntimeError):
            from kraken.build import project

    with pytest.raises(RuntimeError):
        from kraken.build import context
