# Helm

  [Helm]: https://helm.sh/

Package and publish [Helm][] charts to OCI or HTTP(S) registries.

__Quickstart__

```py
# .kraken.py
from kraken.core import Project
from kraken.std.helm import HelmPushTask, HelmPackageTask, helm_settings

helm_settings().add_auth("example.jfrog.io", "me@example.org", "api_token")

project = Project.current()
package = project.task("helmPackage", HelmPackageTask)
package.chart_path.set("./my-helm-chart")
push = project.task("helmPush", HelmPushTask)
push.chart_tarball.set(package.chart_tarball)
push.registry.set("example.jfrog.io/helm-local")
```

## API Documentation

@pydoc kraken.std.helm.HelmSettings

@pydoc kraken.std.helm.helm_settings

@pydoc kraken.std.helm.HelmPackageTask

@pydoc kraken.std.helm.HelmPushTask
