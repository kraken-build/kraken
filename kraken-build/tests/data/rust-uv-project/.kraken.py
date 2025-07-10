import os

from kraken.build import project
from kraken.std import cargo, python
from kraken.std.python.buildsystem.maturin import MaturinZigTarget

settings = python.python_settings(always_use_managed_env=True).add_package_index(
    alias="local",
    index_url=os.environ["LOCAL_PACKAGE_INDEX"],
    credentials=(os.environ["LOCAL_USER"], os.environ["LOCAL_PASSWORD"]),
)
python.install()
python.mypy(version_spec="==1.10.0")
settings.build_system.enable_zig_build(
    targets=[
        MaturinZigTarget(target="x86_64-unknown-linux-gnu", zig_features=[]),
        MaturinZigTarget(
            target="x86_64-pc-windows-msvc",
            zig_features=["pyo3/generate-import-lib"],
        ),
    ]
)
python.publish(package_index="local", distributions=python.build(as_version="0.1.0").output_files)
project.task("python.build").depends_on(cargo.rustup_target_add("x86_64-pc-windows-msvc"))
