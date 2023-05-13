# kraken-wrapper

This projects implements `krakenw`, the wrapper CLI for the Kraken build system that enables reproducible builds
via lock files and executing builds from inside subdirectories.

For more information, check out the [Kraken Documentation](https://kraken-build.github.io/docs/).

__Installation__

You need Python 3.7+, <3.11 (currently limited due to an incompatibility with Dill).

    $ pipx install kraken-wrapper
