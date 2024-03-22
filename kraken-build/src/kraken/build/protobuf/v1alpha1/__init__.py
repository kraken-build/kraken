""" Provides an API for defining a Protobuf project that uses [Buffrs][] for dependency management, [Buf][] for
linting and code-generation capabilities with [grpcio-tools][].

[Buffrs]: https://github.com/helsing-ai/buffrs
[Buf]: https://buf.build/
[grpcio-tools]: https://pypi.org/project/grpcio-tools/

!!! warning "Unstable API"
    This API is unstable and should be consumed with caution.
"""

from .project import protobuf_project, ProtobufProject

__all__ = ["protobuf_project", "ProtobufProject"]
