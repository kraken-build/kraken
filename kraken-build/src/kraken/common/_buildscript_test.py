from kraken.common._buildscript import BuildscriptMetadata, buildscript
from kraken.core import Project


def test_capture_kraken_buildscript(kraken_project: Project) -> None:
    assert buildscript() == BuildscriptMetadata()
    assert buildscript(index_url="http://foo/simple") == BuildscriptMetadata(index_url="http://foo/simple")
    assert buildscript(requirements=["a"]) == BuildscriptMetadata(requirements=["a"])
    assert buildscript(extra_index_urls=["b"]) == BuildscriptMetadata(extra_index_urls=["b"])

    with BuildscriptMetadata.capture() as future:
        buildscript(index_url="c")

    assert future.result() == BuildscriptMetadata(index_url="c")
