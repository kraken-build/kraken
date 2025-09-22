from __future__ import annotations

from unittest.mock import patch

from kraken.core import Project
from kraken.std.python.settings import python_settings
from kraken.std.python.tasks.publish_task import publish


def test_publish_task_uses_uv_publish(kraken_project: Project) -> None:
    """Test that the publish task calls `uv publish` with the correct arguments and env."""

    project = kraken_project

    # Configure the package index in the project settings.
    pypi_url = "https://test.pypi.org/legacy"
    settings = python_settings(project)
    settings.add_package_index(alias="testpypi", credentials=("__token__", "pass"))

    # Create a dummy distribution file.
    dist_dir = project.directory / "dist"
    dist_dir.mkdir()
    dist_file = dist_dir / "my-package-0.1.0.tar.gz"
    dist_file.touch()

    # Create and configure the publish task.
    task = publish(
        package_index="testpypi",
        distributions=[dist_file],
        skip_existing=True,
    )

    # We need to patch subprocess.call since we're not actually running uv.
    with patch("subprocess.call") as mock_call:
        task.execute()

    # Check that `subprocess.call` was called with the `uv publish` command.
    assert mock_call.call_count == 1
    call_args = mock_call.call_args[0][0]
    assert call_args[:3] == ["uv", "publish", "--publish-url"]
    assert call_args[3] == pypi_url
    assert str(dist_file.absolute()) in call_args
    assert "--check-url" in call_args

    # Check that the credentials were passed as environment variables.
    call_kwargs = mock_call.call_args[1]
    assert "env" in call_kwargs
    env = call_kwargs["env"]
    assert env["UV_PUBLISH_USERNAME"] == "__token__"
    assert env["UV_PUBLISH_PASSWORD"] == "pass"
