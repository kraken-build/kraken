from kraken.build.python.v1alpha1 import python_project
from kraken.build.protobuf.v1alpha1 import protobuf_project

proto = protobuf_project()
python_project(codegen = [proto.python])
