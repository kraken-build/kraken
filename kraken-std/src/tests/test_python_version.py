from kraken.std.python.version import git_version_to_python_version


def test__git_version_to_python() -> None:
    assert git_version_to_python_version("0.1.0", False) == "0.1.0"
    assert git_version_to_python_version("0.1.0", True) == "0.1.0"
    assert git_version_to_python_version("0.1.0-alpha.1", False) == "0.1.0a1"
    assert git_version_to_python_version("0.1.0-beta.2", False) == "0.1.0b2"
    assert git_version_to_python_version("0.1.0-rc.3", False) == "0.1.0rc3"
    assert git_version_to_python_version("0.1.0-7-gabcdef", False) == "0.1.0.post0.dev7"
    assert git_version_to_python_version("0.1.0-rc.3-7-gabcdef", False) == "0.1.0rc3.post0.dev7"
    assert git_version_to_python_version("0.1.0-7-gabcdef", True) == "0.1.0.post0.dev7+gabcdef"
