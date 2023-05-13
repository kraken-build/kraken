import os


def get_terminal_width(default: int = 80) -> int:
    """
    Returns the terminal width through :func:`os.get_terminal_size`, falling back to the `COLUMNS` environment
    variable. If neither is available, return *default*.
    """

    try:
        terminal_width = os.get_terminal_size().columns
    except OSError:
        try:
            terminal_width = int(os.getenv("COLUMNS", ""))
        except ValueError:
            terminal_width = default
    return terminal_width
