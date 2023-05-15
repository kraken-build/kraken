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
package = project.do("helmPackage", HelmPackageTask, chart_path="./my-helm-chart")
project.do("helmPush", HelmPushTask, chart_tarball=package.chart_tarball, registry="example.jfrog.io/helm-local")
```

## API Documentation

@pydoc kraken.std.helm.HelmSettings

@pydoc kraken.std.helm.helm_settings

@pydoc kraken.std.helm.HelmPackageTask

@pydoc kraken.std.helm.HelmPushTask
