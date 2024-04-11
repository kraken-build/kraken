from pathlib import Path
from typing import TYPE_CHECKING, Any

from kraken.common import EnvironmentType, RequirementSpec

from ._buildenv_venv import VenvBuildEnv as _VenvBuildEnv

if TYPE_CHECKING:

    def find_uv_bin() -> str:
        ...

else:
    from uv.__main__ import find_uv_bin


class UvBuildEnv(_VenvBuildEnv):
    """Implements a build environment managed by the `uv` package manager.

    This has a lot in common with the `venv` build environment, so we just inherit from it and override the relevant
    parts.
    """

    INSTALLER_NAME = "uv"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._uv_bin = find_uv_bin()

    def _get_create_venv_command(self, python_bin: Path, path: Path) -> list[str]:
        return [self._uv_bin, "venv", str(path)]

    def _get_install_command(self, venv_dir: Path, requirements: RequirementSpec, env: dict[str, str]) -> list[str]:
        env["VIRTUAL_ENV"] = str(venv_dir)
        return [self._uv_bin, "pip", "install", *requirements.to_args()]

    def get_type(self) -> EnvironmentType:
        return EnvironmentType.UV
