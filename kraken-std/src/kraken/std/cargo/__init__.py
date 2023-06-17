""" Provides tasks for Rust projects that build using Cargo. """

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Collection, Sequence

from kraken.common import Supplier
from kraken.core import Project
from typing_extensions import Literal

from .config import CargoConfig, CargoProject, CargoRegistry
from .tasks.cargo_auth_proxy_task import CargoAuthProxyTask
from .tasks.cargo_build_task import CargoBuildTask
from .tasks.cargo_bump_version_task import CargoBumpVersionTask
from .tasks.cargo_check_toolchain_version import CargoCheckToolchainVersionTask
from .tasks.cargo_clippy_task import CargoClippyTask
from .tasks.cargo_deny_task import CargoDenyTask
from .tasks.cargo_fmt_task import CargoFmtTask
from .tasks.cargo_publish_task import CargoPublishTask
from .tasks.cargo_sqlx_migrate import CargoSqlxMigrateTask
from .tasks.cargo_sqlx_prepare import CargoSqlxPrepareTask
from .tasks.cargo_sync_config_task import CargoSyncConfigTask
from .tasks.cargo_test_task import CargoTestTask
from .tasks.cargo_update_task import CargoUpdateTask
from .tasks.rustup_target_add_task import RustupTargetAddTask

__all__ = [
    "cargo_auth_proxy",
    "cargo_build",
    "cargo_bump_version",
    "cargo_clippy",
    "cargo_deny",
    "cargo_fmt",
    "cargo_publish",
    "cargo_registry",
    "cargo_sqlx_migrate",
    "cargo_sqlx_prepare",
    "cargo_sync_config",
    "cargo_update",
    "CargoAuthProxyTask",
    "CargoBuildTask",
    "CargoBumpVersionTask",
    "CargoClippyTask",
    "CargoDenyTask",
    "CargoProject",
    "CargoPublishTask",
    "CargoRegistry",
    "CargoSqlxMigrateTask",
    "CargoSqlxPrepareTask",
    "CargoSyncConfigTask",
    "CargoTestTask",
    "cargo_check_toolchain_version",
    "CargoCheckToolchainVersionTask",
    "rustup_target_add",
    "RustupTargetAddTask",
]

#: This is the name of a group in every project that contains Cargo tasks to contain the tasks that either support
#: or establish pre-requisites for a Cargo build to be executed. This includes ensuring certain configuration is
#: is up to date and the Cargo auth proxy if it is being used.
CARGO_BUILD_SUPPORT_GROUP_NAME = "cargoBuildSupport"
#: This is the name of a group in every project that are pre-requisites for publishing crates within a Cargo workspace.
#: This includes ensuring that all path dependencies have up to date version numbers.
CARGO_PUBLISH_SUPPORT_GROUP_NAME = "cargoPublishSupport"


def cargo_config(*, project: Project | None = None, nightly: bool = False) -> CargoConfig:
    project = project or Project.current()
    config = CargoConfig(nightly=nightly)
    project.metadata.append(config)
    return config


def cargo_sqlx_migrate(
    *, name: str = "sqlxMigrate", project: Project | None = None, **kwargs: Any
) -> CargoSqlxMigrateTask:
    project = project or Project.current()
    return project.do(name, CargoSqlxMigrateTask, **kwargs)


def cargo_sqlx_prepare(
    *, name: str = "sqlxPrepare", project: Project | None = None, check: bool, **kwargs: Any
) -> CargoSqlxPrepareTask:
    project = project or Project.current()
    if check:
        name = f"{name}Check"
        kwargs["group"] = "check"
    task = project.do(name, CargoSqlxPrepareTask, check=check, **kwargs)

    # Preparing or checking sqlx metadata calls `cargo metadata`, which can require the auth proxy
    # Without the auth proxy, cargo sqlx commands would fail with a cryptic error
    # See https://github.com/launchbadge/sqlx/pull/2222 for details
    task.add_relationship(f":{CARGO_BUILD_SUPPORT_GROUP_NAME}?")

    return task


def cargo_registry(
    alias: str,
    index: str,
    read_credentials: tuple[str, str] | None = None,
    publish_token: str | None = None,
    project: Project | None = None,
) -> None:
    """Adds a Cargo registry to the project. The registry must be synced to disk into the `.cargo/config.toml`
    configuration file. You need to make sure to add a sync task using :func:`cargo_sync_config` if you manage
    your Cargo registries with this function. Can be called multiple times.

    :param alias: The registry alias.
    :param index: The registry index URL (usually an HTTPS URL that ends in `.git`).
    :param read_credentials: Username/password to read from the registry (only for private registries).
    :param publish_token: The token to use with `cargo publish`.

    !!! note Artifactory

        It appears that for Artifactory, the *publish_token* must be of the form `Bearer <TOKEN>` where the token
        is a token generated manually via the JFrog UI. It cannot be an API key.
    """

    cargo = CargoProject.get_or_create(project)
    cargo.add_registry(alias, index, read_credentials, publish_token)


def cargo_auth_proxy(*, project: Project | None = None) -> CargoAuthProxyTask:
    """Creates a background task that the :func:`cargo_build` and :func:`cargo_publish` tasks will depend on to
    inject the read credentials for private registries into HTTPS requests made by Cargo. This is only needed when
    private registries are used."""

    project = project or Project.current()
    cargo = CargoProject.get_or_create(project)
    task = project.do(
        "cargoAuthProxy",
        CargoAuthProxyTask,
        False,
        group=CARGO_BUILD_SUPPORT_GROUP_NAME,
        registries=Supplier.of_callable(lambda: list(cargo.registries.values())),
    )
    # The auth proxy is required for both building and publishing cargo packages with private cargo project dependencies
    project.group(CARGO_PUBLISH_SUPPORT_GROUP_NAME).add(task)

    # The auth proxy injects values into the cargo config, the cargoSyncConfig.check ensures that it reflects
    # the temporary changes that should be made to the config. The check has to run before the auth proxy,
    # otheerwise it is garuanteed to fail.
    task.add_relationship(":cargoSyncConfig.check?", strict=False)
    return task


def cargo_sync_config(
    *,
    replace: bool = False,
    project: Project | None = None,
) -> CargoSyncConfigTask:
    """Creates a task that the :func:`cargo_build` and :func:`cargo_publish` tasks will depend on to synchronize
    the `.cargo/config.toml` configuration file, ensuring that the Cargo registries configured with the
    :func:`cargo_registry` function are present and up to date."""

    project = project or Project.current()
    cargo = CargoProject.get_or_create(project)
    task = project.do(
        "cargoSyncConfig",
        CargoSyncConfigTask,
        group="apply",
        registries=Supplier.of_callable(lambda: list(cargo.registries.values())),
        replace=replace,
    )
    check_task = task.create_check()
    project.group(CARGO_BUILD_SUPPORT_GROUP_NAME).add(check_task)
    return task


def cargo_clippy(
    *,
    allow: str = "staged",
    fix: bool = False,
    name: str | None = None,
    group: str | None = "_auto_",
    project: Project | None = None,
) -> CargoClippyTask:
    project = project or Project.current()
    name = "cargoClippyFix" if fix else "cargoClippy"
    group = ("fmt" if fix else "lint") if group == "_auto_" else group
    cargo = CargoProject.get_or_create(project)
    task = project.do(
        name,
        CargoClippyTask,
        False,
        group=group,
        fix=fix,
        allow=allow,
        env=Supplier.of_callable(lambda: cargo.build_env),
    )

    # Clippy builds your code.
    task.add_relationship(f":{CARGO_BUILD_SUPPORT_GROUP_NAME}?")

    return task


def cargo_deny(*, project: Project | None = None, **kwargs: Any) -> CargoDenyTask:
    """Adds a task running cargo-deny for cargo projects. This checks different rules on dependencies, such as scanning
    for vulnerabilities, unwanted licences, or custom bans.

    :param checks: The list of cargo-deny checks to run, as defined in
    https://embarkstudios.github.io/cargo-deny/checks/index.html. If not provided, defaults to all of them.
    :param config_file: The configuration file as defined in https://embarkstudios.github.io/cargo-deny/checks/cfg.html
    If not provided defaults to cargo-deny default location.
    """

    project = project or Project.current()
    return project.do("cargoDeny", CargoDenyTask, **kwargs)


@dataclasses.dataclass
class CargoFmtTasks:
    check: CargoFmtTask
    format: CargoFmtTask


def cargo_fmt(*, all_packages: bool = False, project: Project | None = None) -> CargoFmtTasks:
    project = project or Project.current()
    config = project.find_metadata(CargoConfig) or cargo_config(project=project)
    format = project.do(
        "cargoFmt",
        CargoFmtTask,
        all_packages=all_packages,
        config=config,
        group="fmt",
    )
    check = project.do(
        "cargoFmtCheck",
        CargoFmtTask,
        all_packages=all_packages,
        config=config,
        group="lint",
        check=True,
    )
    return CargoFmtTasks(check=check, format=format)


def cargo_update(*, project: Project | None = None) -> CargoUpdateTask:
    project = project or Project.current()
    task = project.do("cargoUpdate", CargoUpdateTask, group="update")
    task.add_relationship(":cargoBuildSupport", strict=True)

    return task


def cargo_bump_version(
    *,
    version: str,
    revert: bool = True,
    name: str = "cargoBumpVersion",
    group: str | None = CARGO_PUBLISH_SUPPORT_GROUP_NAME,
    registry: str | None = None,
    project: Project | None = None,
    cargo_toml_file: Path = Path("Cargo.toml"),
) -> CargoBumpVersionTask:
    """Get or create a task that bumps the version in `Cargo.toml`.

    :param version: The version number to bump to.
    :param revert: Revert the version number after all direct dependants have run.
    :param name: The task name. Note that if another task with the same configuration but different name exists,
        it will not change the name of the task and that task will still be reused.
    :param group: The group to assign the task to (even if the task is reused)."""

    project = project or Project.current()

    task = project.do(
        name,
        CargoBumpVersionTask,
        group=group,
        version=version,
        revert=revert,
        registry=registry,
        cargo_toml_file=cargo_toml_file,
    )

    task.add_relationship(":test?")

    return task


def cargo_build(
    mode: Literal["debug", "release"],
    incremental: bool | None = None,
    env: dict[str, str] | None = None,
    workspace: bool = False,
    *,
    exclude: Collection[str] = (),
    group: str | None = "build",
    name: str | None = None,
    project: Project | None = None,
) -> CargoBuildTask:
    """Creates a task that runs `cargo build`.

    :param mode: Whether to create a task that runs the debug or release build.
    :param incremental: Whether to build incrementally or not (with the `--incremental=` option). If not
        specified, the option is not specified and the default behaviour is used.
    :param env: Override variables for the build environment variables. Values in this dictionary override
        variables in :attr:`CargoProject.build_env`.
    :param exclude: List of workspace crates to exclude from the build.
    :param name: The name of the task. If not specified, defaults to `:cargoBuild{mode.capitalised()}`.
    :param version: Bump the Cargo.toml version temporarily while building to the given version."""

    assert mode in ("debug", "release"), repr(mode)
    project = project or Project.current()
    cargo = CargoProject.get_or_create(project)

    additional_args = []
    if workspace:
        additional_args.append("--workspace")
    for crate in exclude:
        additional_args.append("--exclude")
        additional_args.append(crate)
    if mode == "release":
        additional_args.append("--release")

    task = project.do(
        f"cargoBuild{mode.capitalize()}" if name is None else name,
        CargoBuildTask,
        default=False,
        group=group,
        incremental=incremental,
        target=mode,
        additional_args=additional_args,
        env=Supplier.of_callable(lambda: {**cargo.build_env, **(env or {})}),
    )
    task.add_relationship(f":{CARGO_BUILD_SUPPORT_GROUP_NAME}?")
    return task


def cargo_test(
    incremental: bool | None = None,
    env: dict[str, str] | None = None,
    *,
    group: str | None = "test",
    project: Project | None = None,
) -> CargoTestTask:
    """Creates a task that runs `cargo test`.

    :param incremental: Whether to build the tests incrementally or not (with the `--incremental=` option). If not
        specified, the option is not specified and the default behaviour is used.
    :param env: Override variables for the build environment variables. Values in this dictionary override
        variables in :attr:`CargoProject.build_env`."""

    project = project or Project.current()
    cargo = CargoProject.get_or_create(project)
    task = project.do(
        "cargoTest",
        CargoTestTask,
        default=False,
        group=group,
        incremental=incremental,
        env=Supplier.of_callable(lambda: {**cargo.build_env, **(env or {})}),
    )
    task.add_relationship(f":{CARGO_BUILD_SUPPORT_GROUP_NAME}?")
    return task


def cargo_publish(
    registry: str,
    incremental: bool | None = None,
    env: dict[str, str] | None = None,
    *,
    verify: bool = True,
    retry_attempts: int = 0,
    additional_args: Sequence[str] = (),
    name: str = "cargoPublish",
    package_name: str | None = None,
    project: Project | None = None,
) -> CargoPublishTask:
    """Creates a task that publishes the create to the specified *registry*.

    :param registry: The alias of the registry to publish to.
    :param incremental: Incremental builds on or off.
    :param env: Environment variables (overrides :attr:`CargoProject.build_env`).
    :param verify: If this is enabled, the `cargo publish` task will build the crate after it is packaged.
        Disabling this just packages the crate and publishes it. Only if this is enabled will the created
        task depend on the auth proxy.
    :param retry_attempts: Retry the publish task if it fails, up to a maximum number of attempts. Sometimes
        cargo publishes can be flakey depending on the destination. Defaults to 0 retries.
    """

    project = project or Project.current()
    cargo = CargoProject.get_or_create(project)

    task = project.do(
        f"{name}/{package_name}" if package_name is not None else name,
        CargoPublishTask,
        False,
        group="publish",
        registry=Supplier.of_callable(lambda: cargo.registries[registry]),
        additional_args=list(additional_args),
        allow_dirty=True,
        incremental=incremental,
        verify=verify,
        retry_attempts=retry_attempts,
        package_name=package_name,
        env=Supplier.of_callable(lambda: {**cargo.build_env, **(env or {})}),
    )

    task.add_relationship(f":{CARGO_PUBLISH_SUPPORT_GROUP_NAME}?")

    return task


def cargo_check_toolchain_version(
    minimal_version: str, *, project: Project | None = None
) -> CargoCheckToolchainVersionTask:
    """Creates a task that checks that cargo is at least at version `minimal_version`"""

    project = project or Project.current()
    return project.do(
        f"cargoCheckVersion/{minimal_version}",
        CargoCheckToolchainVersionTask,
        group=CARGO_BUILD_SUPPORT_GROUP_NAME,
        minimal_version=minimal_version,
    )


def rustup_target_add(target: str, *, group: str | None = None, project: Project | None = None) -> RustupTargetAddTask:
    """Creates a task that installs a given target for Cargo"""

    project = project or Project.current()
    return project.do(f"rustupTargetAdd/{target}", RustupTargetAddTask, group=group, target=target)
