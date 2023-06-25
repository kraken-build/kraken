# Protobuf

  [Buf]: https://buf.build/docs/

Format and lint Proto files using [buf][].

__Quickstart__

```py
# .kraken.py
from kraken.core import Project
from kraken.std.protobuf import BufFormatTask, BufLintTask


project = Project.current()
project.task(name, BufLintTask, group="lint")
project.task(name, BufFormatTask, group="fmt")
```

## Requirements

- The buf lint task will only succeed when executed in a `/proto` directory
- The buf format task can be executed in the root of the project directory and will format inplace all of the proto files that exist in the repo 

## API Documentation

@pydoc kraken.std.protobuf.buf_format

@pydoc kraken.std.protobuf.buf_lint

@pydoc kraken.std.protobuf.BufFormatTask

@pydoc kraken.std.protobuf.BufLintTask

