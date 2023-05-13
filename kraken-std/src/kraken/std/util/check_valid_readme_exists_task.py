from __future__ import annotations

import hashlib
from enum import Enum
from os import listdir
from os.path import isfile, join
from pathlib import Path
from typing import Dict, List

from kraken.core import Project, Property, Task, TaskStatus

README_EXPECTED_FILENAME = "README.md"
README_MIN_LINES = 10
README_CONTENT_NOT_ALLOWED = [
    # Gitlab default readme content hash
    "8be311dad51fc66a430012be31de26d673cfa8ce99a0432097c0d2c778c89b49"
]


class CheckValidReadmeExistsError(Enum):
    DOES_NOT_EXIST = 1
    MULTIPLE_EXIST = 2
    INVALID_FILENAME = 3
    FILE_TOO_SHORT = 4
    CONTENT_NOT_ALLOWED = 5

    def to_description(self) -> str:
        if self == CheckValidReadmeExistsError.DOES_NOT_EXIST:
            return "Readme does NOT exist!"

        if self == CheckValidReadmeExistsError.MULTIPLE_EXIST:
            return "Only one `readme` file is allowed in the root of your repository, you may have more!"

        if self == CheckValidReadmeExistsError.INVALID_FILENAME:
            return f"Invalid `readme` filename, please rename to uppercase > `{README_EXPECTED_FILENAME}`"

        if self == CheckValidReadmeExistsError.FILE_TOO_SHORT:
            return (
                f"There is not enough content in your `readme` file. At least {str(README_MIN_LINES)}"
                + " of non-empty lines of content are expected."
            )

        if self == CheckValidReadmeExistsError.CONTENT_NOT_ALLOWED:
            return (
                "The content of your `readme` is probably a generated default. "
                + "Please add content specific to your project."
            )

        # This should be an impossible state
        return "Unknown `readme` error."


class CheckValidReadmeExistsTask(Task):
    context: Property[Path]

    def execute(self) -> TaskStatus:
        """Performs various validations on the README file!

        Validation rules that we're interested in at the moment:
        - Readme file exists
        - There's only one readme file (for case sensitive OS')
        - Is named as expected (upercase filename with lowercase extension)
        - Has more than an expected number of non-empyt lines
        - Is not one of "bad" not allowed readmes (default / generated ones)
        """
        errors = self._check(self.context.get(), README_CONTENT_NOT_ALLOWED)

        if any(errors.values()):
            # New lines and spaces are used to format the terminal output
            return TaskStatus.failed(
                "\n"
                + "\n".join("    -> " + err.to_description() for err, is_true in errors.items() if is_true)
                + "\n  "
            )

        return TaskStatus.succeeded()

    @staticmethod
    def _check(context: Path, bad_content_hashes: list[str]) -> Dict[CheckValidReadmeExistsError, bool]:
        errors = dict()
        available_files = CheckValidReadmeExistsTask._get_readme_paths(context)

        errors[CheckValidReadmeExistsError.DOES_NOT_EXIST] = len(available_files) == 0
        errors[CheckValidReadmeExistsError.MULTIPLE_EXIST] = len(available_files) > 1

        if len(available_files) == 1:
            readme_file = available_files[0]
            readme_path = context / readme_file

            errors[CheckValidReadmeExistsError.INVALID_FILENAME] = CheckValidReadmeExistsTask._check_file_name(
                readme_file
            )
            errors[CheckValidReadmeExistsError.FILE_TOO_SHORT] = CheckValidReadmeExistsTask._check_line_number(
                readme_path
            )
            errors[
                CheckValidReadmeExistsError.CONTENT_NOT_ALLOWED
            ] = CheckValidReadmeExistsTask._check_content_not_allowed_(readme_path, bad_content_hashes)

        return errors

    @staticmethod
    def _get_readme_paths(directory: Path) -> List[str]:
        proj_files = [f for f in listdir(directory) if isfile(join(directory, f))]
        return list(filter(lambda file_name: "readme.md" == file_name.strip().lower(), proj_files))

    @staticmethod
    def _check_file_name(file_name: str) -> bool:
        # Filename different to expected
        return file_name != README_EXPECTED_FILENAME

    @staticmethod
    def _check_line_number(readme_path: Path) -> bool:
        count = 0
        with open(readme_path) as f:
            for line in f:
                if not line.isspace():
                    count += 1

        # There's less than expected number of non-empty lines in the readme
        return count < README_MIN_LINES

    @staticmethod
    def _check_content_not_allowed_(readme_path: Path, bad_content_hashes: list[str]) -> bool:
        content = ""
        with open(readme_path) as f:
            """Skip the first line of the readme!

            Our assumption is that in most cases project name will be on the first line, which is project specific.

            HOWEVER, if the skipping of the first line fails - ie the file is empty - we return early.

            To make it a bit more robust, we're also ignoring empty lines, so that only the actual textual content is
            made relevant.
            """
            try:
                next(f)
            except StopIteration:
                return False

            for line in f:
                if not line.isspace():
                    content += line

            file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

            """If you have a new file you'd like to add to the list of not allowed hashes, you can run it through this
            code and print the hash, then add it to the list.

                print("HASH >>>> ", file_hash)

            """
            return file_hash in bad_content_hashes


def check_valid_readme_exists(project: Project | None = None) -> CheckValidReadmeExistsTask:
    project = project or Project.current()
    return project.do(
        name="checkValidReadmeExists",
        group="check",
        context=project.directory,
        task_type=CheckValidReadmeExistsTask,
    )
