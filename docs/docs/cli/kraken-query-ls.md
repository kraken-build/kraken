# kraken query ls

<!-- runcmd code: kraken query ls --help | sed -r "s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g" -->
```
usage: kraken query ls [-h] [-v] [-q] [-b PATH] [-p PATH] [--state-name NAME] [--state-dir PATH]
                       [--additional-state-dir PATH] [--no-load-project] [--resume] [--restart {all}] [--all]
                       [task ...]

list all tasks and task groups in the build

options:
  -h, --help                   show this help message and exit

logging options:
  -v                           increase the log level (can be specified multiple times)
  -q                           decrease the log level (can be specified multiple times)

build options:
  -b PATH, --build-dir PATH    the build directory to write to [default: build]
  -p PATH, --project-dir PATH  the root directory of the project. If this is specified, it should point to an existing
                               directory that contains a build script and it must be the same or a parent of the current
                               directory. When invoked with this option, task references are resolved relative to the
                               Kraken project that is represented by the current working directory. (note: this option
                               is automatically passed when using kraken-wrapper as it finds the respective project
                               automatically).
  --state-name NAME            specify a name for the generated state file; if not specified, a short random ID is used
  --state-dir PATH             specify the main build state directory [default: ${--build-dir}/.kraken/buildenv]
  --additional-state-dir PATH  specify an additional state directory to load build state from. can be specified multiple
                               times
  --no-load-project            do not load the root project. this is only useful when loading an existing build state

graph options:
  --resume                     load previous build state
  --restart {all}              load previous build state, but discard existing results (requires --resume)
  --all                        include all tasks in the build graph
  task                         one or more tasks to include in the build graph and mark as selected. if not set, default
                               tasks are included in the build graph but not selected.
```
<!-- end runcmd -->
