from __future__ import annotations

from subprocess import CompletedProcess
from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from kraken.core import Project
from kraken.std.python.settings import python_settings
from kraken.std.python.tasks.publish_task import _get_existing_files_from_index, publish


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
    assert call_args[:5] == [
        "uv",
        "publish",
        "--no-progress",
        "--publish-url",
        pypi_upload_url,
    ]
    assert str(dist_file.absolute()) in call_args

    # Check that the credentials were passed as environment variables.
    call_kwargs = mock_run.call_args[1]
    assert "env" in call_kwargs
    env = call_kwargs["env"]
    assert env["UV_PUBLISH_USERNAME"] == "__token__"
    assert env["UV_PUBLISH_PASSWORD"] == "pass"


def test_get_existing_files_from_index_not_found(httpx_mock: HTTPXMock) -> None:
    """Test that `_get_existing_files_from_index` returns an empty set when the package is not found."""
    httpx_mock.add_response(status_code=404)
    result = _get_existing_files_from_index("my-package", "https://test.pypi.org/simple", None)
    assert result == set()


@pytest.mark.parametrize(
    "content_type, body, expected",
    [
        (
            "application/vnd.pypi.simple.v1+json",
            '{"files": [{"filename": "my-package-0.1.0.tar.gz"}, {"filename": "my-package-0.1.0-py3-none-any.whl"}]}',
            {"my-package-0.1.0.tar.gz", "my-package-0.1.0-py3-none-any.whl"},
        ),
        (
            "text/html",
            '<!DOCTYPE html><html><body><a href=".../my-package-0.1.0.tar.gz#sha256=...">my-package-0.1.0.tar.gz</a></body></html>',
            {"my-package-0.1.0.tar.gz"},
        ),
    ],
)
def test_get_existing_files_from_index_success(
    httpx_mock: HTTPXMock, content_type: str, body: str, expected: set[str]
) -> None:
    """Test that `_get_existing_files_from_index` correctly parses the file list from JSON and HTML responses."""
    httpx_mock.add_response(status_code=200, headers={"Content-Type": content_type}, text=body)
    result = _get_existing_files_from_index("my-package", "https://test.pypi.org/simple", None)
    assert result == expected


def test_get_existing_files_from_index_unsupported_content_type(httpx_mock: HTTPXMock) -> None:
    """Test that `_get_existing_files_from_index` returns None for unsupported content types."""
    httpx_mock.add_response(status_code=200, headers={"Content-Type": "application/octet-stream"})
    result = _get_existing_files_from_index("my-package", "https://test.pypi.org/simple", None)
    assert result is None
