# Protobuf

  [Buf]: https://buf.build/docs/

We currently support automatic linting, formatting and code generation from Protobuf files using [buf][]
and [protoc][] when using the `python_project()` function. 

No local development tools are needed as both `protoc` and `buf` are fetched for you by Kraken.

### Project layout

```
my-project/
  proto/
    my_project/
      service.proto
  src/
    my_project/
      __init__.py
```

Kraken will then generate the following files via the `protoc-python` task:

```
my-proect/
  src/
    my_project/
      .gitignore
      service_pb2.py
      service_pb2_grpc.py
```

The `.gitignore` file contains all the generated files.

### Tasks

The following tasks are created by `python_project()` when a `proto/` directory exists:

* `protoc-python` - Generates Python code from the `.proto` files, including Mypy stub files.
* `buf.lint` - Lints the `.proto` files using [buf][] (group: `lint`)
* `buf.format` - Formats the `.proto` files using [buf][] (group: `fmt`)
