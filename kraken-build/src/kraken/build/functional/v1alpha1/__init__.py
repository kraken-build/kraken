""" This module provides an experimental new functional API for defining Kraken tasks.

This API is marked as `v1alpha1` and should be used with caution. """

from .fetch_file_task import fetch_file
from .fetch_tarball_task import fetch_tarball
from .shell_cmd_task import shell_cmd
from .write_file_task import write_file

__all__ = [
    "write_file",
    "fetch_file",
    "fetch_tarball",
    "shell_cmd",
]
