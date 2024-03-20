# Protobuf

  [Buf]: https://buf.build/docs/
  [Buffrs]: https://github.com/helsing-ai/buffrs
  [Helsing]: https://helsing.ai/

Kraken implements an opinionated workflow for working with Protobuf files, which is currently implemented only for
Python projects using the `python_project()` function. All required tools will be installed for you automatically
by Kraken.

* `buf` via the [Buf] [GitHub releases](https://github.com/bufbuild/buf/releases)
* `buffrs` via its [GitHub releases](https://github.com/helsing-ai/buffrs/releases)
* `protoc` via [grpcio-tools](https://pypi.org/project/grpcio-tools/) (as Pex)

There is currently no opinionated automation for

* Automatically authenticating with a Buffrs registry
* Publishing Buffrs packages

## Buffrs

[Buffrs][] is an opinionated Protobuf dependency manager developed at [Helsing]. It strongly advocates for code
generation in the immediate project that consumes Protobuf APIs instead of publishing pre-generated code to a package
repository. Buffrs is used to manage the Protobuf dependencies in your project.

There are three types of Buffrs projects:

* __Libraries__, which can be depended on by any other Buffrs project and published as Buffrs packages.
* __APIs__, which can be published as Buffrs packages but can _not_ be depended upon by another Library or API.
* __Applications__, which can depend on any Buffrs package, but cannot be published. Typically these only depend on
APIs and do not have any Protobuf files of their own.

When a `Proto.toml` file is detected in a project, Kraken will use `buffrs` to run `buffrs install` to install
dependencies into the `proto/vendor` folder which will be considered the canonical source for Protobuf files to generate code from.

## Projects without Buffrs

Projects without a `Proto.toml` can still be used with Kraken, they simply won't be able to make use of any
kind of dependency management for Protobuf files. In this case, the `proto` directory in your project is considered
the canonical source for Protobuf files to generate code from.

## Python code generation

Kraken will generate Python code in such a way that all APIs can be imported from a `proto` namespace package.

??? note "Packaging Python projects with Protobuf files"
    When packaging a Python project using Protobuf for distribution as a Python package, you have to ensure manually
    that your package manager includes the generated Protobuf files in the package. This is not done automatically by
    Kraken.

    For example, in a Poetry project, you need to amend the packages configuration in `pyproject.toml`:

    ```toml
    [tool.poetry]
    packages = [
        { include = "proto/my_project", from = "src" },
        { include = "src/my_project", from = "src" },
    ]
    ```

=== "With Buffrs"

    __Project structure__

    Given the following project structure:

    ```
    +- Proto.toml
    +- proto/
    |  +- my_project/
    |  |  +- service.proto
    +- src/
    |  +- my_project/
    |  |  +- __init__.py
    ```

    And the following `Proto.toml` file:

    ```toml
    edition = "0.8"

    [dependencies]
    another_service = { version = "^0.1.0" }
    ```

    Running `buffrs install`, which Kraken will do for you automatically, you might end up with the following
    `proto` directory. Note how Buffrs copies your _own_ Protobuf files into `proto/vendor` alongside the dependencies
    to establish a consistent import system.

    ```
    +- proto/
    |  +- vendor/
    |  |  +- another_service/
    |  |  |  +- service.proto
    |  |  +- my_project/
    |  |  |  +- service.proto
    |  +- my_project/
    |  |  +- service.proto
    ```

    __Generated code__

    Kraken will generate the following Python files:

    ```
    +- src/
    |  +- proto/
    |  |  +- .gitignore
    |  |  +- my_project/
    |  |  |  +- __init__.py
    |  |  |  +- service_pb2.py
    |  |  |  +- service_pb2_grpc.py
    |  |  |  +- service_pb2.pyi
    |  |  |  +- service_pb2_grpc.pyi
    |  |  +- another_service/
    |  |  |  +- __init__.py
    |  |  |  +- service_pb2.py
    |  |  |  +- service_pb2.pyi
    |  |  |  +- service_pb2_grpc.py
    |  |  |  +- service_pb2_grpc.pyi
    ```

    __Imports__

    Allowing you to import the generated code like so from your own code in `src/my_project/*`:

    ```python
    from proto.my_project.service_pb2 import MyMessage
    from proto.another_service.service_pb2_grpc import AnotherServiceStub
    # ...
    ```

=== "Without Buffrs"

    __Project structure__

    Given the following project structure:

    ```
    +- proto/
    |  +- my_project/
    |  |  +- service.proto
    +- src/
    |  +- my_project/
    |  |  +- __init__.py
    ```

    __Generated code__

    Kraken will generate the following Python files:

    ```
    +- src/
    |  +- proto/
    |  |  +- .gitignore
    |  |  +- my_project/
    |  |  |  +- __init__.py
    |  |  |  +- service_pb2.py
    |  |  |  +- service_pb2_grpc.py
    |  |  |  +- service_pb2.pyi
    |  |  |  +- service_pb2_grpc.pyi
    ```

    __Imports__

    Allowing you to import the generated code like so from your own code in `src/my_project/*`:

    ```python
    from proto.my_project.service_pb2 import MyMessage
    from proto.my_project.service_pb2_grpc import MyServiceStub
    # ...
    ```

### Tasks

The following tasks are created by `python_project()` when a `proto/` directory exists:

* `protoc-python` - Generates Python code from the `.proto` files, including Mypy stub files.
* `buf.lint` - Lints the `.proto` files using [buf][] (group: `lint`)
* `buf.format` - Formats the `.proto` files using [buf][] (group: `fmt`)
