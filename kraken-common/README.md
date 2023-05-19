# kraken-common

The <u>`kraken-common`</u> package is the shared utility namespace for the Kraken build system and
the Kraken wrapper CLI. It contains various generic utilities, as well as the tools for loading
the metadata of a Kraken project.

Aside from general utilities that are used by one, the other or both, this package also implements the
shared logic for executing Kraken Python and BuildDSL build scripts and retrieving its metadata.

### Script runners

The following types of Kraken script runners are currently available via the `kraken.common` package:

* `PythonScriptRunner`: Matches a `kraken.py` or `.kraken.py` file and runs it as a pure Python script.
* `BuildDslScriptRunner`: Matches a `kraken.build` or `.kraken.build` file and runs it as a [`builddsl`][0]
    script, with the `buildscript()` function being available by default.

[0]: https://niklasrosenstein.github.io/python-builddsl/

### Buildscript metadata

A Kraken project contains at least one `.kraken.py` file (build script) and maybe a `.kraken.lock`
file (lock file). The build script at the root of a project may contain hints for the Kraken wrapper
CLI to be able to correctly bootstrap an environment that contains the Kraken build system.

<table align="center"><tr><th>Python</th><th>BuildDSL</th></tr>
<tr><td>

```py
from kraken.common import buildscript

buildscript(
    requirements=["kraken-std ^0.4.16"],
)
```

</td><td>

```py
buildscript {
    requires "kraken-std ^0.4.16"
}


```

</td></tr></table>

The way that this works is that the `buildscript()` function raises an exception that aborts the execution
of the build script before the rest of the script is executed, and the exception contains the metadata.
When the build script is executed by the Kraken build system instead, the function does nothing.

The API to capture the data passed to a call to the `buildscript()` function is as follows:

```py
from kraken.common import BuildscriptMetadata

with BuildscriptMetadata.capture() as metadata_future:
    ...

metadata = metadata_future.result()
```
