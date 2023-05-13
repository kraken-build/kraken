import contextlib
import copy
import logging
import os
import pprint
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, NoReturn, Sequence

from kraken.common import EnvironmentType, RequirementSpec, lazy_str
from pex.pex import PEX
from pex.pex_bootstrapper import bootstrap_pex_env

from ._buildenv import KRAKEN_MAIN_IMPORT_SNIPPET, BuildEnv, general_get_installed_distributions
from ._lockfile import Distribution
from ._pex import PEXBuildConfig, PEXLayout

logger = logging.getLogger(__name__)


class PexBuildEnv(BuildEnv):
    STYLES = (EnvironmentType.PEX_ZIPAPP, EnvironmentType.PEX_PACKED, EnvironmentType.PEX_LOOSE)

    def __init__(self, style: EnvironmentType, path: Path) -> None:
        assert style in self.STYLES
        self._style = style
        self._path = path

    @contextlib.contextmanager
    def activate(self) -> Iterator[None]:
        assert self._path.exists(), f'expected PEX file at "{self._path}"'
        pex = PEX(self._path)

        state = {}
        for key in ["displayhook", "excepthook", "modules", "path", "path_importer_cache"]:
            state[key] = copy.copy(getattr(sys, key))

        try:
            bootstrap_pex_env(str(pex.path()))
            pex.activate()
            yield
        finally:
            for key, value in state.items():
                setattr(sys, key, value)

    # BuildEnv

    def get_path(self) -> Path:
        return self._path

    def get_type(self) -> EnvironmentType:
        return self._style

    def get_installed_distributions(self) -> List[Distribution]:
        return general_get_installed_distributions([sys.executable, str(self._path)])

    def build(self, requirements: RequirementSpec, transitive: bool) -> None:
        config = PEXBuildConfig(
            interpreter_constraints=(
                [requirements.interpreter_constraint] if requirements.interpreter_constraint else []
            ),
            script="kraken",
            requirements=requirements.to_args(Path.cwd(), with_options=False),
            index_url=requirements.index_url,
            extra_index_urls=list(requirements.extra_index_urls),
            transitive=True,  # Our lockfiles are not fully cross platform compatible (see kraken-wrapper#2)
        )

        layout = {
            EnvironmentType.PEX_ZIPAPP: PEXLayout.ZIPAPP,
            EnvironmentType.PEX_PACKED: PEXLayout.PACKED,
            EnvironmentType.PEX_LOOSE: PEXLayout.LOOSE,
        }[self._style]

        logger.debug("PEX build configuration is %s", lazy_str(lambda: pprint.pformat(config)))

        logger.info('begin PEX resolve for build environment "%s"', self._path)
        installed = config.resolve()

        logger.info('building PEX for build environment "%s"', self._path)
        builder = config.builder(installed)
        builder.build(str(self._path), layout=layout)

    def dispatch_to_kraken_cli(self, argv: List[str]) -> NoReturn:
        with self.activate():
            import logging

            scope: Dict[str, Any] = {}
            exec(KRAKEN_MAIN_IMPORT_SNIPPET, scope)
            main: Callable[[str, Sequence[str]], NoReturn] = scope["main"]

            # We need to un-initialize the logger such that kraken-core can re-initialize it.
            for handler in logging.root.handlers[:]:
                logging.root.removeHandler(handler)

            env_backup = os.environ.copy()
            self.get_type().set(os.environ)

            try:
                main("krakenw", argv)
            finally:
                os.environ.clear()
                os.environ.update(env_backup)

        assert False, "should not be reached"
