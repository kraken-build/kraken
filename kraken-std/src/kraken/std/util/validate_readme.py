from __future__ import annotations

import hashlib
import re
from collections.abc import Generator, Iterator
from pathlib import Path
from typing import Any, TypeVar

from kraken.core import Property, Task, TaskStatus
from kraken.core.cli.executor import status_to_text

T = TypeVar("T")
R = TypeVar("R")


class ValidateReadmeTask(Task):
    """
    This task is intended to be used to validate a README file in a project. It can validate the filename of the
    readme, check if there are multiple readme files, if the file has enough content or matches some disallowed
    content hashes.
    """

    #: The directory in which to check for the readme file.
    directory: Property[Path]

    #: The preferred name(s) of the readme file. If any file that starts with `readme` is found and not one of
    #: these files, it will issue a warning. If none of the preferred files exist, an error is issued.
    preferred_file_names: Property[list[str]] = Property.default_factory(lambda: ["README.md"])

    #: A list of disallowed content hashes. If the readme file matches any of these hashes, an warning is issued.
    #: The first line of the readme will be ignored, as well as empty lines when computing its hash. The key
    #: of the dictionary must contain a name for the hash.
    disallowed_md5_content_hashes: Property[dict[str, str]] = Property.default_factory(dict)

    #: A list of Regex patterns that should not be found in the readme file. If any of these patterns are found,
    #: a warning is issued.
    disallowed_regex_patterns: Property[list[str]] = Property.default_factory(list)

    #: The minimum number of characters that must be present in the readme file. If the readme file has less
    #: than this number of characters, a warning is issued.
    minimum_characters: Property[int] = Property.default(0)

    #: The minimum number of lines that must be present in the readme file. If the readme file has less
    #: than this number of lines, a warning is issued.
    minimum_lines: Property[int] = Property.default(0)

    #: The status of the validation.
    statuses: Property[list[TaskStatus]] = Property.output()

    @staticmethod
    def _find_readme_file(directory: Path, preferred_file_names: list[str]) -> Generator[TaskStatus, None, Path | None]:
        """
        Finds the readme file in the given directory. If no readme file is found, it will yield an error.
        """

        readme_files = [
            item
            for item in directory.iterdir()
            if item.stem.lower() == "readme" or item.stem.lower().startswith("readme.")
        ]

        preferred_readme_files = [item for item in readme_files if item.name in preferred_file_names]
        if not preferred_readme_files:
            yield TaskStatus.failed(
                f"No preferred readme file found (expected one of: {', '.join(x for x in preferred_file_names)})"
            )
            return None

        if len(readme_files) > 1:
            yield TaskStatus.warning(f"Found multiple readme files. Linting only {preferred_readme_files[0].name}")
        else:
            yield TaskStatus.succeeded(f"Found readme file: {preferred_readme_files[0].name}")

        return preferred_readme_files[0]

    @staticmethod
    def _validate_readme_contents(
        path: Path,
        disallowed_md5_content_hashes: dict[str, str],
        disallowed_regex_patterns: list[str],
        minimum_characters: int,
        minimum_lines: int,
    ) -> Iterator[TaskStatus]:
        content = path.read_text()

        if disallowed_md5_content_hashes:
            # Compute the hash of the readme file. We skip the first line; for templatized projects, this is usually
            # the name of the project, which is not relevant for the hash, and ignore empty lines.
            with open(path) as fp:
                fp.readline()
                hashable_content = "\n".join(x for x in fp.readlines() if x.lstrip())
                file_hash = hashlib.md5(hashable_content.encode("utf-8")).hexdigest()

            inverse_hashes = {v: k for k, v in disallowed_md5_content_hashes.items()}
            if file_hash in inverse_hashes:
                yield TaskStatus.warning(f"Readme file content matches disallowed hash '{inverse_hashes[file_hash]}'")
            else:
                yield TaskStatus.succeeded("Readme file content does not match any disallowed hashes")

        if disallowed_regex_patterns:
            for pattern in disallowed_regex_patterns:
                if re.search(pattern, content):
                    yield TaskStatus.warning(f"Readme file contains disallowed pattern {pattern}")
                else:
                    yield TaskStatus.succeeded(f"Readme file does not contain disallowed pattern {pattern}")

        if minimum_characters > 0:
            if len(content) < minimum_characters:
                yield TaskStatus.warning(
                    f"Readme file has less than {minimum_characters} characters (got: {len(content)})"
                )
            else:
                yield TaskStatus.succeeded(
                    f"Readme file has at least {minimum_characters} characters (got: {len(content)})"
                )

        if minimum_lines > 0:
            line_count = content.count("\n")
            if line_count + 1 < minimum_lines:
                yield TaskStatus.warning(f"Readme file has less than {minimum_lines} lines (got: {line_count + 1})")
            else:
                yield TaskStatus.succeeded(f"Readme file has at least {minimum_lines} lines (got: {line_count + 1})")

    def execute(self) -> TaskStatus:
        statuses, readme_file = collect(
            self._find_readme_file(self.directory.get_or(self.project.directory), self.preferred_file_names.get())
        )
        if readme_file is not None:
            statuses += self._validate_readme_contents(
                path=readme_file,
                disallowed_md5_content_hashes=self.disallowed_md5_content_hashes.get(),
                disallowed_regex_patterns=self.disallowed_regex_patterns.get(),
                minimum_characters=self.minimum_characters.get(),
                minimum_lines=self.minimum_lines.get(),
            )

        print(f"    Check results ({len(statuses)})")
        for status in statuses:
            print(f"      {status_to_text(status)}")

        num_checks = len(statuses)
        self.statuses.set(statuses)

        if any(x.is_failed() for x in statuses):
            return TaskStatus.failed(
                f"completed {sum(1 for x in statuses if x.is_failed())} out of {len(statuses)} check(s) with errors"
            )
        elif any(x.is_warning() for x in statuses):
            return TaskStatus.warning(
                f"completed {sum(1 for x in statuses if x.is_warning())} out of {len(statuses)} check(s) with warnings"
            )
        else:
            return TaskStatus.succeeded(f"completed {num_checks} check(s)")


def collect(gen: Generator[T, Any, R]) -> tuple[list[T], R]:
    items = []
    while True:
        try:
            items.append(next(gen))
        except StopIteration as e:
            return items, e.value
