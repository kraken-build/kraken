# `krakenw`

<!-- runcmd code: krakenw --help | sed -r "s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g" -->
```
usage: krakenw [-h] [-V] [-v] [-q] [--use {VENV}] [--status] [--upgrade] [--reinstall] [--uninstall] [--incremental]
               [--show-install-logs] [--no-keyring]
               [cmd ...] ...

This is kraken-wrapper v0.33.1.

krakenw is a thin wrapper around the kraken cli that executes builds in an isolated 
build environment. This ensures that builds are reproducible (especially when using 
lock files).

To learn more about kraken, visit https://github.com/kraken-build/kraken-core.

positional arguments:
  cmd                  {auth,list-pythons,lock} or a kraken command
  args                 additional arguments

options:
  -h, --help           show this help message and exit
  -V, --version        show program's version number and exit

logging options:
  -v                   increase the log level (can be specified multiple times)
  -q                   decrease the log level (can be specified multiple times)

build environment:
  --use {VENV}         use the specified environment type. If the environment type changes it will trigger a reinstall.
                       Defaults to the value of the KRAKENW_USE environment variable. If that variable is unset, and
                       if a build environment already exists, that environment's type will be used. The default
                       environment type that is used for new environments is VENV. [env: KRAKENW_USE=...]
  --status             print the status of the build environment and exit
  --upgrade            reinstall the build environment from the original requirements
  --reinstall          reinstall the build environment from the lock file [env: KRAKENW_REINSTALL=1]
  --uninstall          uninstall the build environment
  --incremental        re-use an existing build environment. Improves installation time after an update to the buildscript
                       dependencies, but does not upgrade all packages to latest. [env: KRAKENW_INCREMENTAL=1]
  --show-install-logs  show Pip install logs instead of piping them to the build/.venv.log/ directory.
                       [env: KARKENW_SHOW_INSTALL_LOGS=1]

authentication:
  --no-keyring         disable the use of the keyring package for loading and storing credentials. [env: KRAKENW_NO_KEYRING=1]

This is kraken-wrapper's help. To show kraken's help instead, run krakenw -- --help
```
<!-- end runcmd -->
