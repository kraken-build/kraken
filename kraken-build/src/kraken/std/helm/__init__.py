"""Build and publish Helm charts with Kraken."""

from __future__ import annotations

import dataclasses
import urllib.parse
from pathlib import Path

from kraken.common import Supplier, http
from kraken.core import Project, Property, Task, TaskStatus

from . import helmapi


@dataclasses.dataclass
class HelmSettings:
    """Project-specific settings for Helm."""

    auth: dict[str, tuple[str, str]] = dataclasses.field(default_factory=dict)
    insecure_registries: set[str] = dataclasses.field(default_factory=set)

    def add_auth(self, host: str, username: str, password: str, insecure: bool = False) -> HelmSettings:
        self.auth[host] = (username, password)
        if insecure:
            self.insecure_registries.add(host)
        return self


def helm_settings(project: Project | None = None) -> HelmSettings:
    """Create or get Helm settings for the project."""

    project = project or Project.current()

    settings = project.find_metadata(HelmSettings)
    if settings is None:
        settings = HelmSettings()
        project.metadata.append(settings)

    return settings


class HelmPackageTask(Task):
    """Packages a Helm chart."""

    # The path to the directory that contains the Helm chart. A relative path is treated relative to
    # the project directory. This property must be set.
    chart_directory: Property[Path]

    # This property specifies the path to the output Helm chart tarball. It can be specified, when the
    # task is created if an explicit output location is desired, otherwise the property will be set
    # when the task was executed and the default output location is in the build directory.
    chart_tarball: Property[Path] = Property.output()

    def execute(self) -> TaskStatus:
        chart_directory = self.project.directory / self.chart_directory.get()
        if self.chart_tarball.is_filled():
            status, output_file = helmapi.helm_package(chart_directory, output_file=self.chart_tarball.get())
        else:
            output_directory = self.project.build_directory / "helm" / self.name
            status, output_file = helmapi.helm_package(chart_directory, output_directory=output_directory)
            if output_file:
                self.chart_tarball.set(output_file)
        if status != 0 or not output_file:
            return TaskStatus.failed()
        return TaskStatus.succeeded()


class HelmPushTask(Task):
    """Pushes a Helm chart to a Helm registry. Supports OCI and HTTP(S) registries."""

    #: The path to the Helm chart package file. This is usually linked with the :attr:`HelmPackageTask.chart_tarball`
    #: output property.
    chart_tarball: Property[Path]

    #: The Helm registry to push to. This can be an HTTP(S) URL to a Helm registry, in which case it must be the full
    #: URL to the remote "directory" where the :attr:`chart_tarball` will be uploaded to. The filename for the chart
    #: in the directory is the basename of :attr:`chart_tarball` unless :attr:`chart_name` is set.
    #:
    #: Alternatively, an `oci://` URL can be specified in which case the `helm push` command is used to push the
    #: chart instead. Note that in this case the :attr:`chart_name` cannot be used and doing so will result in an
    #: error.
    registry: Property[str]

    #: The base name of the chart in the registry. Only when uploading to a HTTP(S) "directory".
    chart_name: Property[str]

    #: The final constructed chart URL that the chart will be published under. Note: This URL is not currently
    #: constructed when pushing to an `oci://` registry and reading the property will cause an error.
    chart_url: Property[str] = Property.output()

    def finalize(self) -> None:
        self.chart_name.setdefault(Supplier.of_callable((lambda: self.chart_tarball.get().name), [self.chart_tarball]))
        return super().finalize()

    def execute(self) -> TaskStatus:
        url = urllib.parse.urlparse(self.registry.get())
        if not url.scheme:
            raise ValueError(f"{self.registry} missing url scheme: {self.registry.get()!r}")
        if url.scheme not in ("oci", "http", "https"):
            raise ValueError(f"{self.registry} invalid url scheme: {self.registry.get()!r}")
        if not url.hostname:
            raise ValueError(f"{self.registry} missing host name: {self.registry.get()!r}")

        settings = helm_settings(self.project)
        credentials: tuple[str, str] | None
        oci_login_host: str | None
        for oci_login_host in (url.hostname, f"{url.hostname}:{url.port}"):
            if oci_login_host in settings.auth:
                credentials = settings.auth[oci_login_host]
                break
        else:
            oci_login_host = None

        if url.scheme == "oci" and credentials:
            self.logger.info("logging into OCI registry %r", url.hostname)
            assert oci_login_host is not None
            command, result = helmapi.helm_registry_login(
                oci_login_host,
                credentials[0],
                credentials[1],
                insecure=oci_login_host in settings.insecure_registries,
            )
            if result != 0:
                return TaskStatus.from_exit_code(command, result)

        if url.scheme == "oci":
            self.chart_url.seterror(f"{self.chart_url} for OCI registries is not currently supported")
            self.logger.info('pushing chart "%s" to OCI registry %r', self.chart_tarball.get(), self.registry.get())
            command, result = helmapi.helm_push(self.chart_tarball.get(), self.registry.get())
            if result != 0:
                return TaskStatus.from_exit_code(command, result)
        elif url.scheme in ("http", "https"):
            self.logger.info(
                'pushing chart "%s" to %s registry %r',
                self.chart_tarball.get(),
                url.scheme.upper(),
                self.registry.get(),
            )
            self.chart_url.set(urllib.parse.urljoin(self.registry.get() + "/", self.chart_name.get()))
            response = http.put(self.chart_url.get(), content=self.chart_tarball.get().read_bytes(), auth=credentials)
            response.raise_for_status()
            self.logger.info("chart url = %s", self.chart_url.get())
        else:
            assert False, url

        return TaskStatus.succeeded()
