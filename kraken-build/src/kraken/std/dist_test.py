import tarfile

from kraken.core import Project, Property, Task
from kraken.core.system.task import TaskStatus
from kraken.std.descriptors.resource import Resource
from kraken.std.dist import dist


def test_dist(kraken_project: Project) -> None:
    """
    This function validates that the #dist() function works as intended with mapping individual options
    to the resources provided by dependencies.
    """

    class ProducerTask(Task):
        result: Property[Resource] = Property.output()

        def execute(self) -> TaskStatus | None:
            output_file = self.project.build_directory / "product.txt"
            output_file.write_text("Hello, World!")
            self.result = Resource(name="file", path=output_file)
            return None

    kraken_project.task("producer", ProducerTask)

    output_archive = kraken_project.build_directory / "archive.tgz"
    dist(name="dist", dependencies={"producer": {"arcname": "result.txt"}}, output_file=output_archive)

    kraken_project.context.execute([":dist"])

    assert output_archive.exists()
    with tarfile.open(output_archive) as tarf:
        fp = tarf.extractfile("result.txt")
        assert fp is not None
        assert fp.read().decode() == "Hello, World!"
