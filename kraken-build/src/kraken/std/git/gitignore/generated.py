from collections.abc import Sequence

from kraken.common.gitignore import GitignoreFile

GENERATED_SECTION_START = "# GENERATED-CONTENT-START"
GENERATED_SECTION_END = "# GENERATED-CONTENT-END"


def split_generated_section(file: GitignoreFile) -> tuple[GitignoreFile, GitignoreFile, GitignoreFile]:
    """
    Splits a GitignoreFile into three parts: the generated section surrounded by the user sections.

    The generated section is marked to start and end with the following comments:

    ```
    # GENERATED-CONTENT-START
    ...
    # GENERATED-CONTENT-END
    ```

    In addition, we support the following format for backwards compatibility for `.gitignore` files
    managed by Kraken 0.26.1 and before:

    ```
    ### START-GENERATED-CONTENT [HASH: ...]

    ### END-GENERATED-CONTENT
    ```

    The middle `GitignoreFile` that is returned will not contain these start and end markers.
    """

    user1 = GitignoreFile()
    generated = GitignoreFile()
    user2 = GitignoreFile()
    target = user1

    it = iter(file)
    entry = next(it, None)
    while entry is not None:
        if entry.type == "comment" and entry.strip() == GENERATED_SECTION_START:
            if target is not user1:
                raise ValueError("Multiple GENERATED-CONTENT-START markers found")
            target = generated
        elif entry.type == "comment" and entry.strip() == GENERATED_SECTION_END:
            if target is not generated:
                raise ValueError("GENERATED-CONTENT-END marker found out of order")
            target = user2

        # Also handle the old format:
        elif entry.type == "comment" and entry.startswith("### START-GENERATED-CONTENT"):
            if target is not user1:
                raise ValueError("Multiple legacy START-GENERATED-CONTENT markers found")
            target = generated
            while True:
                entry = next(it, None)
                if not entry or entry.type != "comment" or entry.startswith("### [PARAMETERS_HASH:"):
                    break
        elif entry.type == "comment" and entry.strip() == "### END-GENERATED-CONTENT":
            if target is not generated:
                raise ValueError("Legacy END-GENERATED-CONTENT marker found out of order")
            if generated and generated[-1].type == "comment" and generated[-1].startswith("# ----"):
                generated.pop()
            target = user2

        else:
            target.append(entry)

        entry = next(it, None)

    return user1, generated, user2


def join_generated_section(user1: Sequence[str], generated: Sequence[str], user2: Sequence[str]) -> GitignoreFile:
    return GitignoreFile.parse([*user1, GENERATED_SECTION_START, *generated, GENERATED_SECTION_END, *user2])
