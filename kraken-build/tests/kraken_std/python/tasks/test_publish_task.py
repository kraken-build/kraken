from __future__ import annotations

from subprocess import CompletedProcess
from unittest.mock import patch

from kraken.core import Project
from kraken.std.python.settings import python_settings
from kraken.std.python.tasks.publish_task import publish


def test_publish_task_uses_uv_publish(kraken_project: Project) -> None:
    """Test that the publish task calls `uv publish` with the correct arguments and env."""

    project = kraken_project

    # Configure the package index in the project settings.
    pypi_upload_url = "https://test.pypi.org/legacy"
    pypi_index_url = "https://test.pypi.org/simple"
    settings = python_settings(project)
    settings.add_package_index(
        alias="testpypi",
        upload_url=pypi_upload_url,
        index_url=pypi_index_url,
        credentials=("__token__", "pass"),
    )

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

    # We need to patch subprocess.run since we're not actually running uv.
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        result = task.execute()

    # Check that the task succeeded and `subprocess.run` was called with the `uv publish` command.
    assert result.is_succeeded()
    assert mock_run.call_count == 1
    call_args = mock_run.call_args[0][0]
    assert call_args[:7] == [
        "uv",
        "publish",
        "--default-index",
        pypi_index_url,
        "--publish-url",
        "--no-progress",
        pypi_upload_url,
    ]
    assert str(dist_file.absolute()) in call_args
    assert "--check-url" not in call_args

    # Check that the credentials were passed as environment variables.
    call_kwargs = mock_run.call_args[1]
    assert "env" in call_kwargs
    env = call_kwargs["env"]
    assert env["UV_PUBLISH_USERNAME"] == "__token__"
    assert env["UV_PUBLISH_PASSWORD"] == "pass"
