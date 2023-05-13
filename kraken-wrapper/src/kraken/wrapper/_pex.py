""" A wrapper around the PEX builder interface. """
from __future__ import annotations

import contextlib
import dataclasses
from pathlib import Path
from typing import Any, Iterator

from pex.pex import PEX
from pex.pex_builder import CopyMode, Layout as PEXLayout, PEXBuilder
from pex.pip.tool import Pip
from pex.platforms import Platform
from pex.resolve.resolver_configuration import PYPI, PasswordEntry, ResolverVersion
from pex.resolve.resolvers import Installed
from pex.resolver import resolve
from pex.targets import Targets
from pex.variables import Variables as PEXVariables

__all__ = [
    "CopyMode",
    "PasswordEntry",
    "PEX",
    "PEXBuildConfig",
    "PEXLayout",
    "PEXVariables",
    "ResolverVersion",
]


@dataclasses.dataclass
class PEXBuildConfig:
    # PEXBuilder
    preamble: str | None = None
    copy_mode: CopyMode = CopyMode.SYMLINK
    interpreter_constraints: list[str] = dataclasses.field(default_factory=list)
    entry_point: str | None = None
    script: str | None = None
    executable: Path | None = None
    shebang: str | None = None

    # PexInfo
    venv_site_packages_copies: bool = True
    emit_warnings: bool = True
    strip_pex_env: bool = False
    use_venv: bool = False

    # Resolver
    requirements: list[str] = dataclasses.field(default_factory=list)
    index_url: str | None = None
    extra_index_urls: list[str] = dataclasses.field(default_factory=list)
    password_entries: list[PasswordEntry] = dataclasses.field(default_factory=list)
    pip_resolver_version: ResolverVersion = ResolverVersion.PIP_LEGACY  # PIP_2020
    platforms: list[str] | None = None
    preserve_log: bool = False
    transitive: bool = True

    def resolve(self) -> Installed:
        if self.platforms is None:
            targets = Targets()
        else:
            targets = Targets(platforms=tuple(Platform.create(x) for x in self.platforms))
        if self.index_url is None:
            indexes = [PYPI]
        else:
            indexes = [self.index_url]
        indexes.extend(self.extra_index_urls)
        return resolve(
            targets=targets,
            requirements=self.requirements,
            indexes=indexes,
            resolver_version=self.pip_resolver_version,
            password_entries=self.password_entries,
            preserve_log=self.preserve_log,
            transitive=self.transitive,
        )

    def builder(self, installed: Installed | None) -> PEXBuilder:
        if installed is None:
            installed = self.resolve()

        pex_builder = PEXBuilder(
            preamble=self.preamble,
            copy_mode=self.copy_mode,
        )

        pex_builder.info.venv_site_packages_copies = self.venv_site_packages_copies
        pex_builder.info.emit_warnings = self.emit_warnings
        pex_builder.info.strip_pex_env = self.strip_pex_env
        pex_builder.info.venv = self.use_venv

        for ic in self.interpreter_constraints:
            pex_builder.add_interpreter_constraint(ic)
        for installed_dist in installed.installed_distributions:
            pex_builder.add_distribution(installed_dist.distribution, fingerprint=installed_dist.fingerprint)
            for direct_req in installed_dist.direct_requirements:
                pex_builder.add_requirement(direct_req)

        if self.entry_point:
            pex_builder.set_entry_point(self.entry_point)
        elif self.script:
            pex_builder.set_script(self.script)
        elif self.executable:
            pex_builder.set_executable(str(self.executable), "__pex_executable__.py")

        if self.shebang:
            pex_builder.set_shebang(self.shebang)

        return pex_builder


@contextlib.contextmanager
def inject_pip_args_for_pex_resolve(args: list[str]) -> Iterator[None]:
    """Inject *args* into the arguments that will be used for the Pex resolve."""

    method_name = "_calculate_resolver_version_args"

    old_method = getattr(Pip, method_name)

    def new_method(cls: type[Pip], *a: Any, **kw: Any) -> Iterator[str]:
        yield from old_method(*a, **kw)
        yield from args

    setattr(Pip, method_name, new_method)
    try:
        yield
    finally:
        setattr(Pip, method_name, old_method)
