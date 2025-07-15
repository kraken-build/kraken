# kraken &lt;aspect&gt;

!!! warning "Experimental"

    Kraken aspects are an experimental feature that might undergo breaking changes. Use with care!

## Overview

Aspects are a new way to interface with the Kraken CLI and control task execution starting with `kraken-build v0.46.0`.

An aspect represents a set of tasks that achieve a similar goal (think "linting", "type checking", etc.) and gives
them a dedicated CLI with a dedicated behaviour for task selection and furthermore allows some level of in-place
configuration of the tasks without modifying the build scripts.

For aspects to be usable, the tasks you want to run through an aspect must explicitly support it an the options that
are available for that aspect.

The following aspects are currently available (see also [`ASPECTS`][kraken.core.system.aspect.ASPECTS]).

!!! info "Options for aspect commands"

    The `kraken <aspect>` commands take all the options available to `kraken run` in addition to the options you can
    see outlined in the command usage below, with a precedence to the `kraken run` options.

    That means you can mix for example the `-v` or `-X,--exclude-subgraph` options with the aspect options, but when
    they overlap, the pseudo argument `--` must be specified, such as for the `--help` argument.

    * `kraken lint --help` will give you the options that are shared by all aspect commands.
    * `kraken lint -- --help` will give you the options for the lint aspect specifically.

### Shared aspect options

<!-- runcmd code: kraken build --help -->

### The `build` aspect

<!-- runcmd code: kraken build -- --help -->

### The `fmt` aspect

<!-- runcmd code: kraken fmt -- --help -->

### The `lint` aspect

<!-- runcmd code: kraken lint -- --help -->

### The `check` aspect

<!-- runcmd code: kraken check -- --help -->

### The `test` aspect

<!-- runcmd code: kraken test -- --help -->

### The `invoke` aspect

!!! note

    The [`RunAspect`][kraken.core.system.aspect.RunAspect] is called `invoke` on the CLI because the `kraken run`
    command is already occupied.

<!-- runcmd code: kraken invoke -- --help -->
