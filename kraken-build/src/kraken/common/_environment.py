import enum
from collections.abc import Mapping, MutableMapping

from deprecated import deprecated

KRAKEN_ENVIRONMENT_TYPE_VARIABLE = "_KRAKEN_COMMONS_ENVIRONMENT_TYPE"


@deprecated(
    reason="Starting with kraken-wrapper v0.45.0, the environment type can no longer be selected and only Uv is supported."
)
class EnvironmentType(enum.Enum):
    """
    This enumeration describes the type of environment that is being used to run Kraken in.
    """

    #: This enum reflects that Kraken was run directly, without being invoked through Kraken wrapper.
    NATIVE = 0

    #: Wrapper, using a virtual environment.
    VENV = 1

    #: Use the new shiny `uv` package manager.
    UV = 2

    def is_wrapped(self) -> bool:
        """Whether the environment is managed by Kraken-wrapper."""
        return self != EnvironmentType.NATIVE

    @staticmethod
    def get(environ: Mapping[str, str]) -> "EnvironmentType":
        value = environ.get(KRAKEN_ENVIRONMENT_TYPE_VARIABLE, EnvironmentType.NATIVE.name)
        try:
            return EnvironmentType(value)
        except ValueError:
            raise RuntimeError(
                f"The value of environment variable {KRAKEN_ENVIRONMENT_TYPE_VARIABLE}={value!r} is invalid, "
                f"valid values are {', '.join(x.name for x in EnvironmentType)}. The most likely cause of this "
                "error is that the version of kraken-wrapper and kraken-build are incompatible."
            )

    def set(self, environ: MutableMapping[str, str]) -> None:
        environ[KRAKEN_ENVIRONMENT_TYPE_VARIABLE] = self.name
