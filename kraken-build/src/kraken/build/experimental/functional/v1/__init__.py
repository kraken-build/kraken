""" This module provides an experimental new functional API for defining Kraken tasks. """

from .write_file_task import write_file
from .fetch_file_task import fetch_file
from .fetch_tarball_task import fetch_tarball
from .shell_cmd_task import shell_cmd

__all__ = [
    "write_file",
    "fetch_file",
    "fetch_tarball",
    "shell_cmd",
]
