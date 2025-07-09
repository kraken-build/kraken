import hashlib
import logging
from dataclasses import dataclass, field
from fnmatch import fnmatch
from os import fspath
from pathlib import Path
from typing import Any, Protocol

from stablehash import stablehash
from typing_extensions import Buffer

from kraken.common._fs import safe_rmpath
from kraken.core.system.task import Task

logger = logging.getLogger(__name__)


class Hasher(Protocol):
    def update(self, data: Buffer, /) -> None: ...
    def hexdigest(self) -> str: ...


@dataclass
class BuildCache:
    """
    A helper class that aids in the implementation of caching in tasks.

    Using a `BuildCache` object must follow a strict sequence of method calls to ensure correctness and to avoid
    mistakes.

    1. Populate the input hash by calling :meth:`consume` or :meth:`consume_path` with the data that influences the output.
    2. Finalize the input hash by calling :meth:`finalize`. The :meth:`consume` and :meth:`consume_path` methods can no
    longer be called after this.
    3. Call :meth:`staging_key` or :meth:`staging_path` to get the staging directory for the task's results. The methods
    cannot be called before the cache has been finalized.
    4. Call :meth:`commit` to finalize the cache and move the staging directory to the final cache directory.
    5. Call the :meth:`store_key` or :meth:`store_path` to get the final cache directory. These methods can only be
    called after the cache has been committed. You can also use the :meth:`link_result` method to create a link to a
    file or directory in the finalized cache.

    It is recommended to use the `BuildCache` class as a context manager, which ensures that the cache is cleaned up
    using the :meth:`abort` method if an exception occurs during the execution of the task before :meth:`commit` is
    called.

    A typical usage pattern looks like this:

    .. code-block:: python

        with BuildCache.for_(task) as cache:
            cache.consumes(data)
            cache.consumes_path(path)
            cache.finalize()

            if cache.exists():
                cache.link_result("output.txt", task.output_file)
                return TaskStatus.skipped("Cache hit")
            else:
                # Perform the task's work and write the output to the staging directory
                cache.staging_path().mkdir(parents=True, exist_ok=True)
                cache.commit()
                cache.link_result("output.txt", task.output_file)
                return TaskStatus.succeeded("Task completed successfully")
    """

    suffix: str
    input_hasher: Hasher
    store_directory: Path
    finalized: bool = False
    committed: bool = False
    staged_links: list[tuple[str | Path, Path]] = field(default_factory=list)
    exclude_paths: list[str] = field(default_factory=list)

    @staticmethod
    def for_(task: Task) -> "BuildCache":
        return BuildCache(
            suffix="-" + task.address.name,
            store_directory=task.project.context.build_directory / ".store",
            input_hasher=hashlib.new("sha1"),
            # TODO: We might need a more generic way to exclude paths.
            exclude_paths=[fspath(task.project.context.build_directory.resolve()), ".venv", ".git", "*.egg-info"],
        )

    def consumes(self, data: Any) -> None:
        """
        Include the given *data* in the hash calculation. The *data* can be any Python object that is hashable by the
        :class:`stablehash` library, which includes most built-in types, including lists, dictionaries and data classes.
        """

        if self.finalized:
            raise RuntimeError("Cannot consume data after the cache has been finalized.")

        self.input_hasher.update(stablehash(data).digest())

    def consumes_path(self, path: Path, strict: bool = True) -> None:
        """
        Include the given *path* in the hash calculation. The *path* is hashed by reading its contents. If the path
        points to a directory, all files in the directory are recursively hashed. If the path does not exist, it is
        ignored unless `strict` is set to `True` (default), in which case an error is raised.
        """

        if self.finalized:
            raise RuntimeError("Cannot consume path after the cache has been finalized.")

        if not path.exists():
            if strict:
                raise FileNotFoundError(f"Path '{path}' does not exist.")
            return

        # TODO: We can make the exclusion check more effective by walking through the directory tree instead of
        #       using rglob() and skipping an entire directory if it is excluded.

        path = path.resolve()

        def is_excluded(child: Path) -> bool:
            child_fspath = fspath(child)
            for pattern in self.exclude_paths:
                if "/" not in pattern:
                    pattern = "*/" + pattern + "/*"
                if child_fspath.startswith(pattern):
                    return True
                if fnmatch(child_fspath, pattern):
                    return True
            return False

        if path.is_file():
            if is_excluded(path):
                return
            with path.open("rb") as f:
                self.input_hasher.update(fspath(path).encode("utf-8"))
                self.input_hasher.update(f.read())
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    if is_excluded(child):
                        continue
                    with child.open("rb") as f:
                        self.input_hasher.update(fspath(child).encode("utf-8"))
                        self.input_hasher.update(f.read())

    def finalize(self) -> None:
        """
        Finalize the cache, meaning that no further data can be consumed to alter the hash. This is useful to ensure
        that the hash remains stable and does not change after the cache has been created.
        """

        self.finalized = True

        staging_path = self.staging_path()
        if staging_path.exists():
            logger.warning("Staging path '%s' already exists, removing it", staging_path)
            safe_rmpath(staging_path)

    def staging_key(self) -> str:
        """
        Returns the staging name for the cache, which is a unique directory to put the task's results in before it
        is deemed final and successful.
        """

        if not self.finalized:
            raise RuntimeError("Cannot get staging key before the cache has been finalized.")

        return f"{self.input_hasher.hexdigest()}{self.suffix}.staging"

    def staging_path(self) -> Path:
        """
        Returns the full staging path for the cache, based on the store directory and the :meth:`staging_key` method.
        """

        return self.store_directory / self.staging_key()

    def commit(self) -> None:
        """
        Commit the cache by renaming the staging directory to the final cache directory.
        """

        if not self.finalized:
            raise RuntimeError("Cannot commit cache before it has been finalized.")

        final_path = self.store_path(_force=True)
        final_path_exists = final_path.exists()

        staging_path = self.staging_path()
        if not staging_path.exists():
            if final_path_exists:
                return
            raise FileNotFoundError(f"Staging path '{staging_path}' does not exist.")

        if final_path.exists():
            raise FileExistsError(f"Cache already exists at '{final_path}'.")

        logger.debug("Committing cache from '%s' to '%s'", staging_path, final_path)
        staging_path.rename(final_path)
        self.committed = True

        for source, target in self.staged_links:
            self.link_result(source, target)
        self.staged_links.clear()

    def abort(self) -> None:
        """
        Abort the cache by removing the staging directory. This is useful to clean up the cache if it is no longer
        needed, and should be called when the task fails or is not successful.
        """

        if self.finalized:
            safe_rmpath(self.staging_path())

    def store_key(self, *, _force: bool = False) -> str:
        """
        Return the final key for the cache in the store directory.

        Cannot be called before the cache has been committed.
        """

        if not _force and not self.committed:
            raise RuntimeError("Cannot get store key before the cache has been committed.")
        return f"{self.input_hasher.hexdigest()}{self.suffix}"

    def store_path(self, *, _force: bool = False) -> Path:
        """
        Return the path to the cache directory in the store directory. The path is created based on the unique name
        returned by :meth:`store_name`. Note that this method finalizes the cache, meaning that no further data can be
        consumed to alter the hash.
        """

        return self.store_directory / self.store_key(_force=_force)

    def exists(self) -> bool:
        """
        Check if the cache exists in the store directory.
        """

        return self.store_path(_force=True).exists()

    def remove(self) -> None:
        """
        Remove the cache directory from the store directory. This is useful to clean up the cache if it is no longer
        needed, and should be called when the task
        """

        safe_rmpath(self.store_path())

    def link_result(self, source: str | Path, target: Path) -> None:
        """
        A helper method to link the *source* file to the *target* path. This is useful to create a link to the cached
        result in the store directory. If the target already exists, it is removed before creating the link.

        If this is called before the cache has been committed, it will be queued and executed on commit.
        """

        if not self.committed:
            self.staged_links.append((source, target))
        else:
            source = self.store_path() / source
            if not source.exists():
                raise FileNotFoundError(f"Source file '{source}' does not exist.")
            if target.exists():
                logger.debug("Removing existing result '%s'", target)
                safe_rmpath(target)
            logger.debug("Linking '%s' to '%s'", source, target)
            target.symlink_to(source.resolve(), source.is_dir())

    def __enter__(self) -> "BuildCache":
        """
        Enter the context manager, which allows the cache to be used in a `with` statement. This is useful to ensure
        that the cache is deleted if any exception occurs during inside the `with` block.
        """

        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: Any) -> None:
        if exc_type is not None:
            self.abort()
        else:
            if not self.committed:
                self.commit()
