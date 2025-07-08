from pathlib import Path

from kraken.common.supplier import Supplier
from kraken.core import Project, Property, Task
from kraken.std.util.render_file_task import RenderFileTask, render_file


class BaseBuildTask(Task):
    """Base class for tasks that build Docker images. Subclasses implement converting the task properties into
    the invocation for a Docker build backend."""

    build_context: Property[Path]
    dockerfile: Property[Path] = Property.default(Path("Dockerfile"))
    auth: Property[dict[str, tuple[str, str]]] = Property.default_factory(dict)
    platform: Property[str]
    build_args: Property[dict[str, str]] = Property.default_factory(dict)
    secrets: Property[dict[str, str]] = Property.default_factory(dict)
    cache_repo: Property[str | None] = Property.default(None)
    cache: Property[bool] = Property.default(True)
    tags: Property[list[str]] = Property.default_factory(list)
    push: Property[bool] = Property.default(False)
    squash: Property[bool] = Property.default(False)
    target: Property[str | None] = Property.default(None)
    image_output_file: Property[Path | None] = Property.default(None)
    load: Property[bool] = Property.default(False)

    # If enabled, a separate Dockerfile preprocessing task will be created during finalize().
    # Implementations that typically require processing will enable this property by default.
    preprocess_dockerfile: Property[bool] = Property.default(False)

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.build_context.set(project.directory)
        self.preprocessor_task: RenderFileTask | None = None

    def _preprocess_dockerfile(self, dockerfile: Path) -> str:
        """Internal. Can be implemented by subclasses. Preprocess the Dockerfile."""

        return dockerfile.read_text()

    def create_preprocessor_task(self, group: str | None = None) -> RenderFileTask:
        assert self.preprocess_dockerfile.get(), f"no preprocessing requested: {self}"
        assert not self.preprocessor_task, f"preprocessor task already exists: {self.preprocessor_task}"
        tempfile = self.project.build_directory / self.name / "Dockerfile"
        dockerfile = self.dockerfile.value
        task = render_file(
            name=self.name + ".preprocess",
            description="Preprocess the Dockerfile.",
            create_check=False,
            group=group,
            file=tempfile,
            content=Supplier.of_callable(lambda: self._preprocess_dockerfile(dockerfile.get()), [dockerfile]),
            project=self.project,
        )[0]
        self.dockerfile.set(task.file)
        self.preprocessor_task = task
        return task

    # Task

    def finalize(self) -> None:
        if not self.preprocessor_task and self.preprocess_dockerfile.get():
            self.create_preprocessor_task()
        return super().finalize()
