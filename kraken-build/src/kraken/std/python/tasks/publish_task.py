from __future__ import annotations

import os
import subprocess
import urllib.parse
from collections.abc import Iterable
from html.parser import HTMLParser
from pathlib import Path

import httpx
from loguru import logger
from packaging.utils import canonicalize_name

from kraken.core import Project, Property, Task, TaskRelationship
from kraken.core.system.task import TaskStatus

from ..settings import python_settings


class PublishTask(Task):
    """Publishes Python distributions to one or more indexes using `uv publish`."""

    description = "Upload the distributions of your Python project. [index url: %(index_upload_url)s]"
    index_upload_url: Property[str]
    index_index_url: Property[str]
    index_credentials: Property[tuple[str, str] | None] = Property.default(None)
    distributions: Property[list[Path]] = Property.output()
    skip_existing: Property[bool] = Property.default(False)
    interactive: Property[bool | None] = Property.default(None)
    dependencies: list[Task]

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.dependencies = []

    def get_relationships(self) -> Iterable[TaskRelationship]:
        yield from (TaskRelationship(task, True, False) for task in self.dependencies)
        yield from super().get_relationships()

    def prepare(self) -> TaskStatus | None:
        if not self.skip_existing.get():
            return None

        distributions = self.distributions.get()
        if not distributions:
            return TaskStatus.skipped("No distributions to publish.")

        project_name = distributions[0].name.split("-")[0]
        existing_files = _get_existing_files_from_index(
            project_name, self.index_index_url.get(), self.index_credentials.get()
        )
        self.logger.debug("Existing files in index: %s", existing_files)

        # If we can't check, proceed to execute and let uv handle it.
        if existing_files is None:
            return None

        files_to_publish = [dist for dist in distributions if dist.name not in existing_files]

        if not files_to_publish:
            return TaskStatus.skipped("All distribution files already exist on the index.")

        # Update the distributions to only publish the ones that don't exist.
        self.distributions.set(files_to_publish)
        return None

    def execute(self) -> TaskStatus:
        # Check for the deprecated property
        if self.interactive.get() is not None:
            self.logger.warning(
                "The 'interactive' property on the python.publish task is deprecated and has no effect. "
                "uv publish is non-interactive by default in this context."
            )
        credentials = self.index_credentials.get()
        command = [
            "uv",
            "publish",
            "--no-progress",  # No spinners and progress bars in stderr
            "--publish-url",
            self.index_upload_url.get(),
        ]
        distributions = self.distributions.get()
        if not distributions:
            return TaskStatus.succeeded("No new distributions to publish.")

        command.extend([str(x.absolute()) for x in distributions])

        env = {}
        if credentials:
            if "pypi.org/" in self.index_upload_url.get() and credentials[0] != "__token__":
                self.logger.warning(
                    "Since 2024-01-01, PyPI no longer allows publishing with username and password, "
                    " see https://blog.pypi.org/posts/2024-01-01-2fa-enforced/"
                    " and https://docs.astral.sh/uv/guides/package/#publishing-your-package"
                )
            env["UV_PUBLISH_USERNAME"] = credentials[0]
            env["UV_PUBLISH_PASSWORD"] = credentials[1]

        self.logger.info("$ %s", command)

        result = subprocess.run(
            command,
            cwd=self.project.directory,
            env={**os.environ, **env},
            capture_output=True,
            text=True,
            check=False,
        )

        return TaskStatus.from_exit_code(command, result.returncode)


def _get_existing_files_from_index(
    project_name: str, index_url: str, credentials: tuple[str, str] | None
) -> set[str] | None:
    """Get a set of all existing files for a project from the repository index.

    Returns None if the check cannot be performed.
    """

    # PEP 503: Names should be normalized.
    # See https://packaging.python.org/en/latest/specifications/name-normalization/#name-normalization
    normalized_name = canonicalize_name(project_name)
    logger.debug(f"Index URL: {index_url}")
    url = urllib.parse.urljoin(f"{index_url}/", f"{normalized_name}/")
    logger.debug(f"Normalised package index URL: {url}")
    # For valid Content-Types,
    # see https://packaging.python.org/en/latest/specifications/simple-repository-api/#content-types
    headers = {
        "Accept": ",".join(
            (
                "application/vnd.pypi.simple.v1+json",
                "application/vnd.pypi.simple.v1+html",
                "application/json",
                "text/html",
            )
        )
    }

    try:
        response = httpx.get(url, auth=credentials, headers=headers, follow_redirects=True)

        if response.status_code == 404:
            # Package not found, so no files exist.
            logger.debug(f"Project {project_name} (normalized to {normalized_name}) not found.")
            return set()

        if response.status_code != 406:
            response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        logger.debug(f"PyPI server content type: {content_type}")
        if "application/json" in content_type or "application/vnd.pypi.simple.v1+json" in content_type:
            data = response.json()
            return {file_info["filename"] for file_info in data.get("files", [])}
        elif "text/html" in content_type or "application/vnd.pypi.simple.v1+html" in content_type:
            # NOTE: pypiserver used in tests currently only supports the HTML API
            # See https://github.com/pypiserver/pypiserver/issues/508
            logger.debug(f"Falling back to HTML parsing for PyPI index at {index_url}")

            class SimpleApiParser(HTMLParser):
                def __init__(self) -> None:
                    super().__init__()
                    self.files: set[str] = set()

                def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                    if tag == "a":
                        for attr, value in attrs:
                            if attr == "href" and value:
                                # The href can be a relative URL and may contain a hash fragment.
                                path = urllib.parse.urlparse(value).path
                                filename = path.split("/")[-1]
                                self.files.add(urllib.parse.unquote(filename))

            parser = SimpleApiParser()
            parser.feed(response.text)
            return parser.files
        else:
            logger.warning(
                f"Unsupported Content-Type '{content_type}' from PyPI index at {index_url}. "
                "Cannot check for existing files."
            )
            return None

    except httpx.RequestError as e:
        logger.warning(f"Failed to connect to PyPI index at {url} to check for existing files. Error: {e}")
        return None
    except Exception as e:
        logger.warning(f"An unexpected error occurred while checking for existing files on {url}. Error: {e}")
        return None


def publish(
    *,
    package_index: str,
    distributions: list[Path] | Property[list[Path]],
    skip_existing: bool = False,
    interactive: bool | None = None,
    name: str = "python.publish",
    group: str | None = "publish",
    project: Project | None = None,
    after: list[Task] | None = None,
) -> PublishTask:
    """Create a publish task for the specified registry."""

    project = project or Project.current()
    settings = python_settings(project)
    if package_index not in settings.package_indexes:
        raise ValueError(f"package index {package_index!r} is not defined")

    index = settings.package_indexes[package_index]
    task = project.task(name, PublishTask, group=group)
    task.index_upload_url = index.upload_url
    task.index_index_url = index.index_url
    task.index_credentials = index.credentials
    task.distributions = distributions
    task.skip_existing = skip_existing
    task.interactive = interactive
    task.depends_on(*(after or []))
    return task
