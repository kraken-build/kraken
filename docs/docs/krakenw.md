# Kraken wrapper

`krakenw` is the CLi for interacting with Kraken-powered projects.

* It acts as a wrapper around the `kraken` CLI, so everything you read in the [Command-line documentation](./cli/kraken.md) applies to `krakenw` as well.
* It adds various quality of life features to building projects with Kraken, such as being able to run it from inside sub-directories and resolving task names relative to the current directory.
* It ensures reproducible builds by installing Kraken and its dependencies into its own Python virtual environment and locking the versions of all dependencies in a `.kraken.lock` file.
* It manages credentials keyed by host name for use in authenticating with Python package indexes when using an alternative `index_url` in your build script's requirements (see below). These credentials can also be read at build time by the Kraken build system to authenticate with the same hosts.

## Installation

To use `krakenw`, you need to have Python 3.10 or newer installed. You can install `krakenw` using `pipx`:

```bash
pipx install kraken-wrapper
```

## Usage

To use `krakenw` with your project, you first need to define the requirements for your build script in the `.kraken.py` file at the root of your project. This allows `krakenw` to understand the Python packages to install in the isolated build environment to successfully run the build script. [See [`buildscript()`](#kraken.common.buildscript) for more information on how to do this.]

Once you've defined the requirements, you can use the `krakenw` command as a drop-in replacement for `kraken` and it will ensure to install the required dependencies into a virtual environment before evaluating your build script and executing the build. The only exception to this are commands that are added by the `krakenw` CLI itself, such as `krakenw lock` and `krakenw auth`.

Your typical use of the `krakenw` CLI will look like this:

```bash
$ krakenw auth <hostname> -u <username> -p <password>
$ krakenw --upgrade lock
$ krakenw run <task-name> [<task-name> ...]
$ krakenw query tree --all
```

Note that all options accepted by `krakenw` itself (such as `--upgrade`) must be specified before the first positional argument. All arguments including the first positional argument are passed to the `kraken` CLI. This includes the `-v,--verbose` flag that is supported separately by `krakenw` and `kraken`; hence the following two commands have different semantics:

```bash
$ krakenw -v run <task-name>
$ krakenw run -v <task-name>
```

## Build environments and lock files

Kraken-wrapper creates a Python virtual environment at the project's top-level directory in a folder called `build/.kraken/venv`. This virtual environment is where the dependencies defined with the [`buildscript()`](#kraken.common.buildscript) function are installed.

The `krakenw lock` command creates a `.kraken.lock` file that contains the details of your current build environment. Note that this file is always created based on the _currently installed_ packages in the build environment. If you updated the requirements in the `buildscript()` function call in `.kraken.py`, you need to run `krakenw --upgrade lock` to first upgrade the build environment before running `krakenw lock` to update the lock file.

The build environment, lock file and `.kraken.py` file may run out of sync. You can check the current status of all three using the `krakenw --status` command:

```
$ krakenw --status
Key                    Source                                           Value                                                           
---------------------  -----------------------------------------------  ----------------------------------------------------------------
Requirements           /home/niklas/git/kraken/.kraken.py               653652d98e5ae05d045dc0348db23bfad63ed0224c82d0c835047a7afe1ff4dc
Lockfile               /home/niklas/git/kraken/.kraken.lock             -                                                               
  Requirements hash                                                     653652d98e5ae05d045dc0348db23bfad63ed0224c82d0c835047a7afe1ff4dc
  Pinned hash                                                           a71eab8ae7fd3e3f2059fb272598682c159d86e8c97a941da2cd44ec8179c9c5
Environment            /home/niklas/git/kraken/build/.kraken/venv       VENV                                                            
  Metadata             /home/niklas/git/kraken/build/.kraken/venv.meta  -                                                               
    Created at                                                          2024-02-15T22:25:53.903815                                      
    Requirements hash                                                   a71eab8ae7fd3e3f2059fb272598682c159d86e8c97a941da2cd44ec8179c9c5
```

This output tells you the following:

* The source of the build script requirements (your `.kraken.py` file) and the hash sum of these requirements.
* The path to the lock file and the hash sum of
    * (1) the pinned requirements, which must match with the hash sum of the requirements in the build script, and
    * (2) the hash sum of the pinned requirements, which must match with the hash sum of the installed packages in the build environment.
* The path to the build environment and the hash sum of the installed packages in the build environment, as well as the
    installer that was used for the build environment. For more information on available installers, see below.

## Installers

Kraken-wrapper supports different installers that can materialize your build environment. The default is `VENV` which uses the `venv` module from the Python standard library to create a virtual environment and then `pip` to install requirements.

Since `v0.34.0`, Kraken-wrapper also supports the `UV` installer which uses [uv](https://astral.sh/blog/uv) to create the virtual environment and install requirements. Uv is a new project in its early stages, but is generally faster than the `VENV` installer by a factor of 10-20x. To use the `UV` installer, you have the following options:

1. Set the `KRAKENW_USE=UV` environment variable.
2. Pass the `--use=UV` option to the `krakenw` command when installing your environment.

## Credentials managment

The `krakenw auth` command can be used to store credentials for a given hostname in the system keyring. Any `index_url` or `extra_index_url` in your build script's requirements that matches the hostname will use these credentials to authenticate with the package index.

!!! note
    If no backend for the `keyring` package is available, kraken-wrapper will fall back to writing the password as plain text into the `~/.config/krakenw/config.toml` configuration file. A warning will be printed to inform you about this.

## Building subprojects

The `kraken` CLI supports running in a sub project, but requires that you point it to the root of your project using
the `-p,--project-dir` option. The `krakenw` CLI will automatically find the root of your project and pass it to the
`kraken` CLI for you. This means that you can run `krakenw` from anywhere in your project and it will behave as if you
had run it from the root of your project but in the context of the current directory. Relative addresses passed to the
CLI will be considered relative to the Kraken project of the current directory.

For example, if you have a project with the following structure:

    .
    ├── .kraken.py
    └── sub-project
        └── .kraken.py

And you have a task `:t` in the sub-project, you can run it from the root of your project or the sub-project with
the `kraken` CLI like thisL

    (.)           $ kraken run sub-project:t
    (sub-project) $ kraken run t -p ..

And with the `krakenw` CLI like this:

    (.)           $ krakenw run sub-project:t
    (sub-project) $ krakenw run t

If you want to stop `krakenw` from crawling up the directories until it finds the `.git` project's top level directory
and the top-most Kraken build script, you can add `# ::krakenw-root` as a comment to the top of your build script in
a sub-directory. This allows you to effectively treat a sub-directory as a separate Kraken project.

## Environment variables

Krakenw considers the following environment variables:

| Variable | Effect |
| -------- | ------ |
| `KRAKENW_USE` | The installer to use for the build environment. Can be `VENV` or `UV`. |
| `KRAKENW_REINSTALL` | If set to `1`, the build environment will be reinstalled. This is analogous to passing `--reinstall` on the CLI. |
| `KRAKENW_INCREMENTAL` | If set to `1`, the latest requirements will be installed into the existing environment without first deleting it. This is analogous to passing `--incremental` on the CLI. |
| `KRAKENW_NO_KEYRING` | If set to `1`, the keyring package will not be used to store credentials. This is analogous to passing `--no-keyring` on the CLI. |

## `krakenw --help`

<!-- runcmd code: krakenw --help | sed -r "s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g" -->
<!-- end runcmd -->

## API Documentation

::: kraken.common.buildscript
    options:
      show_signature: false
      show_source: false
