# Cargo

  [Rust]: https://www.rust-lang.org/
  [Cargo]: https://doc.rust-lang.org/cargo/
  [rust-lang/cargo#10592]: https://github.com/rust-lang/cargo/pull/10592

Build [Rust][] projects with [Cargo][].

__Features__

* Supports private Crate registries by injecting Basic-auth credentials using a HTTPS proxy.

__Quickstart__

```py
# ::requirements kraken-std

from kraken.std.cargo import *

cargo_registry( 
    "artifactory",
    "https://example.jfrog.io/artifactory/git/test-cargo.git",
    publish_token=f"Bearer <TOKEN>",
    read_credentials=("me@example.org", "<TOKEN>"),
)
cargo_auth_proxy()
cargo_sync_config()
cargo_build("debug")
cargo_build("release")
cargo_publish("artifactory")
```

__Integration tests__

The `cargo_publish()` and `cargo_build()` tasks are continuously integration tested against JFrog Artifactory
and Cloudsmith.

__Build graph__

![](https://i.imgur.com/EMh0u9q.png)

## API Documentation

@pydoc kraken.std.cargo.cargo_registry
@pydoc kraken.std.cargo.cargo_auth_proxy
@pydoc kraken.std.cargo.cargo_sync_config
@pydoc kraken.std.cargo.cargo_fmt
@pydoc kraken.std.cargo.cargo_build
@pydoc kraken.std.cargo.cargo_publish
@pydoc kraken.std.cargo.cargo_update
@pydoc kraken.std.cargo.cargo_deny
@pydoc kraken.std.cargo.cargo_hack

## Environment variables

* `PROXY_PY_TIMEOUT`
* `KRAKEN_CARGO_BUILD_FLAGS`
