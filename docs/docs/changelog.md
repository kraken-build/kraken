# Changelog

<!-- runcmd cd .. && slap changelog format --all --markdown -->
## Unreleased

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

Upgrade Dill to `>=0.3.8,<0.4.0` which added support for Python 3.11+</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
</table>

## 0.33.1 (2024-01-12)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

Use `--upgrade-deps` option to `python -m venv` instead of calling `pip install --upgrade pip` separately after Venv creation</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Accept `str` for `pytest(tests_dir, ignore_dirs, include_dirs)` arguments</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Store a `.success.flag` file in the virtual build environment to know if the Virtual environment installation was successful.</td><td></td><td><a href="https://github.com/kraken-build/kraken/issues/24">24</a></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Fix</td><td>

Catch `Property.Deferred` exception in `kraken query describe`
</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Update Python `PublishTask` to use Twine as a PEX, removing the `twine` dependency in `kraken-build` itself, and adding the `--verbose` flag</td><td></td><td><a href="https://github.com/kraken-build/kraken/issues/165">165</a></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Use latest Pip version and resolver in Pex, and use `--venv prepend` for Novella</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
</table>

## 0.33.0 (2024-01-10)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Feature</td><td>

Add `version_spec` argument to `black()`, `flake8()`, `isort()`, `mypy()`, `pycln()`, `pylint()` and `pyupgrade()` factory functions</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Drastically improve the performance of `kraken.common.findpython.get_candidates()` on Windows and WSL where you would until now test the entire C:/Windows/System32 folder for executable access.</td><td></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

Add `kraken.build` module which allows importing the current `context` and `project` from a build script as if calling `Context.current()` or `Project.current()`</td><td></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

Add a `PexBuildTask` and add support for most Python tooling tasks to defer to an alternative binary (which the DAG builder can use to point to a PEX)</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
</table>

## 0.32.6 (2024-01-07)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Feature</td><td>

Add sqlx database create and drop tasks</td><td></td><td></td><td>nicolas.vizzari@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

`Currentable.as_current()` now returns self</td><td></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

Add `pytest(include_dirs)` to add additional directories for testing</td><td></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.32.4 (2023-12-14)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

Remove PEX code from Kraken-wrapper. No one is using that!</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
</table>

## 0.32.3 (2023-12-14)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

Relax Python version constraint for the kraken-wrapper, but we still recommend using Python 3.10 for Kraken because of Dill</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
</table>

## 0.32.2 (2023-12-14)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Breaking change</td><td>

Move `kraken-wrapper` code back into its own package, remove `kraken-core`, `kraken-common` and `kraken-std` (those are not usually depended on directly at the moment anyway)</td><td><a href="https://github.com/kraken-build/kraken/pull/141">141</a></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Fix</td><td>

Fixed a bug in `--all` option supported by all graph commands (e.g. `kraken run` and the `kraken query` commands) that made the argument not recognized.</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
</table>

## 0.32.1 (2023-12-13)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

Enable cargo:token as a global-credential-provider; this is required since 1.74, which brings authenticated priviate registries</td><td><a href="https://github.com/kraken-build/kraken/pull/140">140</a></td><td></td><td>quentin.santos@helsing.ai</td></tr>
</table>

## 0.32.0 (2023-12-12)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

Merge `kraken-common`, `kraken-core`, `kraken-std` and `kraken-wrapper` packages into a single `kraken-build` package.</td><td><a href="https://github.com/kraken-build/kraken/pull/125">125</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Calling `buildscript()` from a Kraken project that is not the root project will now raise a `RuntimeError`.</td><td><a href="https://github.com/kraken-build/kraken/pull/130">130</a></td><td><a href="https://github.com/kraken-build/kraken/issues/124">124</a></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Remove use of `pkg_resources` and replace it with `importlib.metadata` and `packaging.requirements` instead.</td><td><a href="https://github.com/kraken-build/kraken/pull/129">129</a></td><td><a href="https://github.com/kraken-build/kraken/issues/126">126</a></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Add flag to run all workspace tests</td><td><a href="https://github.com/kraken-build/kraken/pull/135">135</a></td><td></td><td>@asmello</td></tr>
  <tr><td>Fix</td><td>

Accept gitconfig with several occurrences of the same section</td><td><a href="https://github.com/kraken-build/kraken/pull/136">136</a></td><td></td><td>@qsantos</td></tr>
  <tr><td>Breaking change</td><td>

Remove `kraken.std.http` module, use `kraken.common.http` instead</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Tests</td><td>

Add a unit test for a real-world example of a DAG that failed the expected behavior of `TaskGraph.mark_tasks_as_skipped()`.</td><td><a href="https://github.com/kraken-build/kraken/pull/138">138</a></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Fix</td><td>

Replace `Tasks.mark_tasks_as_skipped()` with a simpler implementation that also fixes an issues with second-degree tasks being marked as skipped even if they should not be.</td><td><a href="https://github.com/kraken-build/kraken/pull/138">138</a></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Fix</td><td>

Allow extra keys when parsing the Cargo manifest `[bin]` section</td><td><a href="https://github.com/kraken-build/kraken/pull/139">139</a></td><td><a href="https://github.com/kraken-build/kraken/issues/134">134</a></td><td>niklas.rosenstein@helsing.ai</td></tr>
</table>

## 0.31.7 (2023-10-10)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Feature</td><td>

Added buffrs login/install/generate to kraken.std. Allow cargo_build to depend on task(s), i.e. buffrs install</td><td><a href="https://github.com/kraken-build/kraken-build/pull/120">kraken-build/kraken-build#120</a></td><td></td><td>alex.spencer@helsing.ai</td></tr>
  <tr><td>Fix</td><td>

Confine buf command to current working directory of project</td><td><a href="https://github.com/kraken-build/kraken-build/pull/122">kraken-build/kraken-build#122</a></td><td></td><td>alex.spencer@helsing.ai</td></tr>
</table>

## 0.31.6 (2023-09-28)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

Improve errors that could be raised by the `TaskGraph` when a `not_none()` expectation is not met.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/119">kraken-build/kraken-build#119</a></td><td></td><td>rosensteinniklas@gmail.com</td></tr>
  <tr><td>Fix</td><td>

Fixed to recompute hash for `Address` after deserialization.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/121">kraken-build/kraken-build#121</a></td><td></td><td>rosensteinniklas@gmail.com</td></tr>
</table>

## 0.31.5 (2023-09-19)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

Set `docker buildx build --provenance=false` by default to avoid pushing a list manifest by default.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/118">kraken-build/kraken-build#118</a></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.31.4 (2023-09-19)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

Fixed a bug where tasks that are dependencies of another task excluded with the `-X` option (recursive exclude) would be tagged unconditionally to be skipped during execution even if it was still required by another task that is not skipped.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/116">kraken-build/kraken-build#116</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Fix</td><td>

Pyupgrade: support properly relative source and test directories</td><td><a href="https://github.com/kraken-build/kraken-build/pull/103">kraken-build/kraken-build#103</a></td><td></td><td>thomas.pellissier-tanon@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Properly exposes Maturin project builder env variable setter</td><td><a href="https://github.com/kraken-build/kraken-build/pull/113">kraken-build/kraken-build#113</a></td><td></td><td>thomas.pellissier-tanon@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Removed krakenw Nix flake</td><td><a href="https://github.com/kraken-build/kraken-build/pull/74">kraken-build/kraken-build#74</a></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Mask auth password and check validity</td><td><a href="https://github.com/kraken-build/kraken-build/pull/112">kraken-build/kraken-build#112</a></td><td></td><td>alex.spencer@helsing.ai</td></tr>
  <tr><td>Fix</td><td>

Update poetry lock to fix nix build</td><td><a href="https://github.com/kraken-build/kraken-build/pull/114">kraken-build/kraken-build#114</a></td><td></td><td>alex.spencer@helsing.ai</td></tr>
</table>

## 0.31.3 (2023-09-14)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Refactor</td><td>

Add http module to common</td><td><a href="https://github.com/kraken-build/kraken-build/pull/109">kraken-build/kraken-build#109</a></td><td></td><td>alex.spencer@helsing.ai</td></tr>
  <tr><td>Deprecation</td><td>

Deprecate http module in std in preference of moving to kraken-common</td><td><a href="https://github.com/kraken-build/kraken-build/pull/109">kraken-build/kraken-build#109</a></td><td></td><td>alex.spencer@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Allows to inject env variable in Maturin builds</td><td><a href="https://github.com/kraken-build/kraken-build/pull/104">kraken-build/kraken-build#104</a></td><td></td><td>@Tpt</td></tr>
  <tr><td>Improvement</td><td>

add `mode=max,ignore-error=true` to the `--cache-to=type=registry,...` option created by the `BuildxBuildTask`.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/111">kraken-build/kraken-build#111</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Fix</td><td>

Enforces isort and refreshes poetry.lock</td><td><a href="https://github.com/kraken-build/kraken-build/pull/108">kraken-build/kraken-build#108</a></td><td></td><td>@Tpt</td></tr>
</table>

## 0.31.2 (2023-09-04)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

Fixed log format string when Pip fails to install dependencies.</td><td></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.31.1 (2023-08-22)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

Added the ability to specify additional directories to run Python linting tasks againt.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/90">kraken-build/kraken-build#90</a></td><td></td><td>@cowlingjosh</td></tr>
  <tr><td>Improvement</td><td>

Added get_lockfile() to PythonBuildSystem subclasses as common way to retrieve the lock file</td><td><a href="https://github.com/kraken-build/kraken-build/pull/101">kraken-build/kraken-build#101</a></td><td></td><td>alex.waldenmaier@icloud.com</td></tr>
  <tr><td>Fix</td><td>

Fixed a bug in Pythons `InstallTask` that would accidentally always cause the install task to run even if that was disabled.</td><td></td><td></td><td>rosensteinniklas@gmail.com</td></tr>
  <tr><td>Improvement</td><td>

Expose all environment variables understood by `krakenw` as CLI options as well and document the variables in the `--help` text.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/79">kraken-build/kraken-build#79</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

Add `--show-install-logs` to the CLI and handle the `KRAKENW_SHOW_INSTALL_LOGS` env var.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/79">kraken-build/kraken-build#79</a></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.31.0 (2023-08-08)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

Rework task description wrapping</td><td><a href="https://github.com/kraken-build/kraken-build/pull/98">kraken-build/kraken-build#98</a></td><td><a href="https://github.com/kraken-build/kraken-build/issues/93">kraken-build/kraken-build#93</a></td><td>jon.gjengset@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Wrap error message in a map</td><td><a href="https://github.com/kraken-build/kraken-build/pull/97">kraken-build/kraken-build#97</a></td><td></td><td>nicolas.vizzari@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Avoids building the Maturin library twice with PDM</td><td><a href="https://github.com/kraken-build/kraken-build/pull/99">kraken-build/kraken-build#99</a></td><td></td><td>@Tpt</td></tr>
  <tr><td>Improvement</td><td>

Makes PDM integration test mandatory</td><td><a href="https://github.com/kraken-build/kraken-build/pull/86">kraken-build/kraken-build#86</a></td><td></td><td>@Tpt</td></tr>
  <tr><td>Feature</td><td>

Facilitates the creation of Debian packages from Rust projects.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/87">kraken-build/kraken-build#87</a></td><td></td><td>@morosanmihail</td></tr>
  <tr><td>Feature</td><td>

Allows passing features to cargo_build and cargo_test.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/77">kraken-build/kraken-build#77</a></td><td></td><td>@morosanmihail</td></tr>
</table>

## 0.30.4 (2023-08-04)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

Add error message in paramaters of function</td><td><a href="https://github.com/kraken-build/kraken-build/pull/96">kraken-build/kraken-build#96</a></td><td></td><td>nicolas.vizzari@helsing.ai</td></tr>
</table>

## 0.30.2 (2023-08-03)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Feature</td><td>

Allow to pass a custom error message for `cargo_deny`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/95">kraken-build/kraken-build#95</a></td><td></td><td>nicolas.vizzari@helsing.ai</td></tr>
</table>

## 0.30.1 (2023-08-03)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

Makes flake8 happy</td><td><a href="https://github.com/kraken-build/kraken-build/pull/91">kraken-build/kraken-build#91</a></td><td></td><td>@Tpt</td></tr>
  <tr><td>Fix</td><td>

Makes flake8 happy</td><td><a href="https://github.com/kraken-build/kraken-build/pull/91">kraken-build/kraken-build#91</a></td><td></td><td>@Tpt</td></tr>
  <tr><td>Fix</td><td>

Correct multi-line description wrapping</td><td><a href="https://github.com/kraken-build/kraken-build/pull/94">kraken-build/kraken-build#94</a></td><td><a href="https://github.com/kraken-build/kraken-build/issues/93">kraken-build/kraken-build#93</a></td><td>@jonhoo</td></tr>
  <tr><td>Improvement</td><td>

Report python coverage in terminal.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/92">kraken-build/kraken-build#92</a></td><td></td><td>benjamin.poumarede@helsing.ai</td></tr>
</table>

## 0.30.0 (2023-07-31)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

Upgrades GitHub actions dependencies</td><td><a href="https://github.com/kraken-build/kraken-build/pull/85">kraken-build/kraken-build#85</a></td><td></td><td>@Tpt</td></tr>
  <tr><td>Fix</td><td>

Fixed an issue where cargo managed by nix would not be recognised as such, due to the which command being unable to follow symlinks.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/80">kraken-build/kraken-build#80</a></td><td></td><td>@ivan-jukic</td></tr>
  <tr><td>Breaking change</td><td>

Adds support of Maturin+PDM Python projects</td><td><a href="https://github.com/kraken-build/kraken-build/pull/84">kraken-build/kraken-build#84</a></td><td></td><td>@Tpt</td></tr>
  <tr><td>Feature</td><td>

do not unnecessarily sort path</td><td><a href="https://github.com/kraken-build/kraken-build/pull/83">kraken-build/kraken-build#83</a></td><td></td><td>james.baker@helsing.ai</td></tr>
</table>

## 0.29.0 (2023-07-13)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

Enforces 3.10+ type annotation syntaxes using pyupgrade</td><td><a href="https://github.com/kraken-build/kraken-build/pull/62">kraken-build/kraken-build#62</a></td><td></td><td>@Tpt</td></tr>
  <tr><td>Improvement</td><td>

Support pytest coverage.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/48">kraken-build/kraken-build#48</a></td><td></td><td>benjamin.poumarede@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Add `--no-http2` to the mitmproxy when invoked via the Cargo auth proxy task. This is to work around an issue with Cargo HTTP/2 multi-plexing (see https://github.com/rust-lang/cargo/issues/12202).</td><td><a href="https://github.com/kraken-build/kraken-build/pull/75">kraken-build/kraken-build#75</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

add Nix flake</td><td><a href="https://github.com/kraken-build/kraken-build/pull/73">kraken-build/kraken-build#73</a></td><td></td><td>james.baker@helsing.ai</td></tr>
  <tr><td>Fix</td><td>

Fixed a bug in the ordering of Python interpreters when resolving an appropriate installation for the Kraken build environment. We now rely on the order returned by `kraken.common.findpython.get_candidates()`, which already attempts to be a bit clever in the order it returns candidates (e.g. `python3` over `python3.X` over `python3.X.Y` over installations in `~/.pyenv/versions`).</td><td><a href="https://github.com/kraken-build/kraken-build/pull/76">kraken-build/kraken-build#76</a></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.28.4 (2023-07-11)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Feature</td><td>

Add `PythonInstallTask.skip_if_venv_exists` property (defaults to true) and `PythonSettings.skip_install_if_venv_exists` flag.;</td><td></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.28.3 (2023-07-10)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

Raise min Python version to 3.7</td><td></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

The wrapper does not have an issue with Python 3.11 as the core does due to Dill, so we should allow installing it into 3.11 and newer.</td><td></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.28.2 (2023-07-10)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

mitmproxy: Stream HTTP body instead of buffering to completion</td><td><a href="https://github.com/kraken-build/kraken-build/pull/71">kraken-build/kraken-build#71</a></td><td></td><td>@wngr</td></tr>
</table>

## 0.28.1 (2023-07-10)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

The `DaemonController.run()` function now creates the parent directory of the stdout/stderr output files by default.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/70">kraken-build/kraken-build#70</a></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.28.0 (2023-07-07)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

Handle `DaemonController` state more defensively.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/68">kraken-build/kraken-build#68</a></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.28.0.dev0 (2023-07-07)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Deprecation</td><td>

Deprecate `Property.config()`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/64">kraken-build/kraken-build#64</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

Add `Property.required()` and a `help` parameter to `Property.output()`, `Property.default()` and `Property.default_factory()`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/64">kraken-build/kraken-build#64</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

Add `Task.add_tag()`, `Task.remove_tag()` and `Task.get_tags()`. A "skip" tag can now be added to a task to skip it.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/66">kraken-build/kraken-build#66</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Allow `Task` items in parameter to `Context.resolve_tasks()`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/66">kraken-build/kraken-build#66</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Tests</td><td>

Test `PythonBuildSystem.build()` with `as_version` set for Slap/Poetry/Pdm</td><td></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Adjust task property definitions to replace `Property.config()` with `Property.default()` and `Property.default_factory()`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/64">kraken-build/kraken-build#64</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Breaking change</td><td>

Move Kraken task definitions in `kraken.std.docker` into `kraken.std.docker.tasks` module</td><td><a href="https://github.com/kraken-build/kraken-build/pull/66">kraken-build/kraken-build#66</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Phase out `proxy.py` MITM proxy for Cargo repositories and replace it with `mitmproxy` (https://mitmproxy.org/). Kraken will now start `mitmweb` in the background listening to port `8899` (same as before), while serving the Web Interface on port `8900`. The `mitmweb` process will remain alive over multiple runs of Kraken and restart automatically if its configuration changes (e.g. if the token changes).</td><td><a href="https://github.com/kraken-build/kraken-build/pull/68">kraken-build/kraken-build#68</a></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.27.5 (2023-06-30)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

Do not call `PdmPyprojectHandler.set_path_dependencies_to_version()` in `PDMPythonBuildSystem.build()` as its not yet supported.</td><td></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.27.4 (2023-06-28)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

Fixed `cargo_sqlx_migrate()` and `cargo_sqlx_prepare()` by adding missing parameters that were previously supported with `**kwargs` before `Project.do()` was deprecated.</td><td></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.27.3 (2023-06-28)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

Handle `keyring.backends.null` the same as the fail backend -- i.e. as if no keyring backend is available. Improve logs to show the available keyring backend.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/61">kraken-build/kraken-build#61</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

If the selected keyring backend is `null`, add a log to prompt the user to re-enable keyring</td><td><a href="https://github.com/kraken-build/kraken-build/pull/61">kraken-build/kraken-build#61</a></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.27.2 (2023-06-28)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

Do not sort out `python3.XY` and `python3.XY.AB` binaries when searching for candidates of Python binaries on the system in `kraken.common.findpython.get_candidates()`.</td><td></td><td><a href="https://github.com/kraken-build/kraken-build/issues/60">kraken-build/kraken-build#60</a></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.27.0 (2023-06-27)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Feature</td><td>

Add `kraken.common.strings` module with the `as_bytes()` function</td><td><a href="https://github.com/kraken-build/kraken-build/pull/51">kraken-build/kraken-build#51</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

Add `kraken.common.strings.as_string()`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/56">kraken-build/kraken-build#56</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Replace more references to deprecated `Task.path` and `Project.path` with the new `.address` attribute</td><td></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Get rid of `pretty_errors` again, experience has shown that it does not provide the added value that we hoped for as it still just outputs a Python traceback, but now in a different format than people are used to.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/49">kraken-build/kraken-build#49</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Handle common errors in the Kraken CLI to improve the user experience.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/49">kraken-build/kraken-build#49</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

Add `TaskStatusType.WARNING`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/50">kraken-build/kraken-build#50</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

Support `Literal` type hints in `Property`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/50">kraken-build/kraken-build#50</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Breaking change</td><td>

The `kraken.core.testing` Pytest fixtures now always create a Context and Project in temporary directories. The temporary directories are distinct, this helps in ensuring that we do not accidentally depend on the current working directory or the project directory being somehow related to the Context directory.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/50">kraken-build/kraken-build#50</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Breaking change</td><td>

Moved `as_bytes()` from `kraken.core.lib.check_file_contents_task` to `kraken.common.strings`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/51">kraken-build/kraken-build#51</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

Add `Property.is_set()` which returns `True` if `Property.set()` (or its variants) have not been called before and if the property does not have a default value.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/51">kraken-build/kraken-build#51</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

Add `Project.task()` overload to create tasks, which deprecated `Project.do()`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/54">kraken-build/kraken-build#54</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Deprecation</td><td>

Deprecate `Project.do()` in favor of `Project.task()`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/54">kraken-build/kraken-build#54</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Add `Address.normalize(keep_container)` keyword argument.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/54">kraken-build/kraken-build#54</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Fix</td><td>

Fixed `Context.resolve_tasks()` when `None` is passed, which is intended to resolve only the default tasks in the current project and its subprojects. Before this fix, the method would return _all_ tasks of the current project instead, because the address `.` would be treated like a single-element address, such as `lint`, which gets turned into `:**:.` (or `:**:lint`).</td><td><a href="https://github.com/kraken-build/kraken-build/pull/54">kraken-build/kraken-build#54</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

Add `Project.task(name, closure)` overload that can be used in BuildDSL build scripts to define custom tasks. It creates an instance of an `InlineTask`, which also allows adding properties dynamically.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/54">kraken-build/kraken-build#54</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

The `Property` class is now a Python descriptor, allowing to assign property values to tasks using assignments in addition to `set()`. Assigning `None` to it will set it to `None` for optional properties, and clear it for non-optional properties.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/54">kraken-build/kraken-build#54</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Fix</td><td>

Fix `kraken query tree` command to remove the `--no-save` option and to never save the build context to disk after the command.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/54">kraken-build/kraken-build#54</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Breaking change</td><td>

Move `kraken.core.lib.render_file_task` and `kraken.core.lib.check_file_contents_task` to `kraken.std.util`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/56">kraken-build/kraken-build#56</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

When a build fails, the summary of which tasks have not been executed no longer include groups.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/57">kraken-build/kraken-build#57</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Breaking change</td><td>

Reimplement `CheckFileExistsAndIsCommitedTask` as `CheckFileTask` and move it into the `kraken.core.git.tasks` module.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/50">kraken-build/kraken-build#50</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Breaking change</td><td>

Reimplement `CheckValidReadmeExistsTask` as `ValidateReadmeTask`.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/50">kraken-build/kraken-build#50</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Breaking change</td><td>

Re-implement `GitignoreSyncTask`, simplifying the code by a lot (e.g. no more tracking of a generated content hash) and cache a subset of tokens from gitignore.io to distribute them as part of kraken-std. The old begin/end markers we used in gitignore files before is still supported. We also no longer sort the gitignore file entries.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/51">kraken-build/kraken-build#51</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Use Poetry index priority instead of deprecated default/secondary options</td><td><a href="https://github.com/kraken-build/kraken-build/pull/46">kraken-build/kraken-build#46</a></td><td></td><td>sam.rogerson@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Refactor how data is read and written to a Pyproject dependening on the underlying Project management tool (Poetry, PDM, etc.)</td><td><a href="https://github.com/kraken-build/kraken-build/pull/46">kraken-build/kraken-build#46</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Improved PDM implementation to ensure that it targets its own in-project environment instead of a potentially already activated virtual environment in the users terminal when they run Kraken.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/46">kraken-build/kraken-build#46</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

bump Cargo.toml version before building, not only before publishing</td><td><a href="https://github.com/kraken-build/kraken-build/pull/52">kraken-build/kraken-build#52</a></td><td></td><td>jerome.froissart@helsing.ai</td></tr>
  <tr><td>Breaking change</td><td>

Correct name of `mypy_stubtest_task` module and remove backwards compatibility for `mypy_subtest()` function name.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/54">kraken-build/kraken-build#54</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Breaking change</td><td>

Update signature of `info()` function to align with the rest of the task factory functions (e.g. automatically take the current project and build system).</td><td><a href="https://github.com/kraken-build/kraken-build/pull/54">kraken-build/kraken-build#54</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Make parameters to task factory functions in `kraken.std.python.tasks` explicit and change `List` properties to contain a `Sequence`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/54">kraken-build/kraken-build#54</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

Move `kraken.core.lib.render_file_task` and `kraken.core.lib.check_file_contents_task` to `kraken.std.util`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/56">kraken-build/kraken-build#56</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

The `CheckFileContentsTask` will now print a diff by default if the file it checks is not up to date.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/56">kraken-build/kraken-build#56</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

The `CargoSyncConfigTask` now has a `crates_io_protocol` option, which defaults to `sparse`. This means Cargo builds by default use the sparse protocol from now on.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/58">kraken-build/kraken-build#58</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Now sets the `KRAKENW=1` environment variable to allow the Kraken-Core CLI to detect if it is run through `krakenw`.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/49">kraken-build/kraken-build#49</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Fix</td><td>

Fixed passing the `-p` option to the `kraken` command by appending it to the arguments, allowing to use `krakenw query` subcommands from subdirectories.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/54">kraken-build/kraken-build#54</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

Treat `# ::krakenw-root` comment in build scripts to avoid searching up higher for the project root directory.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/54">kraken-build/kraken-build#54</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Set default verbosity of `krakenw` command to 1, ensuring that `INFO` logs are always printed.</td><td></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.26.1 (2023-06-20)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

Catch potential permission error when inspecting the files on the `PATH` in `kraken.common.findpython.get_candidates()`</td><td></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.26.0 (2023-06-19)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

Use `rich`'s logging handler, add `kraken.common.exceptions` module</td><td><a href="https://github.com/kraken-build/kraken-build/pull/45">kraken-build/kraken-build#45</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Breaking change</td><td>

Remove `deprecated_get_requirement_spec_from_file_header()` function</td><td><a href="https://github.com/kraken-build/kraken-build/pull/45">kraken-build/kraken-build#45</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Breaking change</td><td>

Remove deprecated `Project.children()` method and deprecated `Project.subproject()` overloads.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/44">kraken-build/kraken-build#44</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Breaking change</td><td>

Change `Addressable.address` into a read-only property</td><td><a href="https://github.com/kraken-build/kraken-build/pull/44">kraken-build/kraken-build#44</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Make `Project` a subclass of the new `KrakenObject` class</td><td><a href="https://github.com/kraken-build/kraken-build/pull/44">kraken-build/kraken-build#44</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Deprecation</td><td>

Deprecate `Project.path` and `Project.resolve_tasks()`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/44">kraken-build/kraken-build#44</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Deprecation</td><td>

Deprecated `Task.outputs`, `Task.path` and `Task.add_relationship()`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/44">kraken-build/kraken-build#44</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Breaking change</td><td>

Remove `Task.capture`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/44">kraken-build/kraken-build#44</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

Add `Task.depends_on()` and `Task.required_by()`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/44">kraken-build/kraken-build#44</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Fix</td><td>

Move `Address.Element` class definition to the global scope, as otherwise we run into an issue with Dill deserialization where the type of `Address.elements` items is not actually the `Address.Element` type that we can access at runtime. (See https://github.com/uqfoundation/dill/issues/600).</td><td><a href="https://github.com/kraken-build/kraken-build/pull/44">kraken-build/kraken-build#44</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Breaking change</td><td>

`TaskGraph` implementation now stores `Address` keys instead of strings</td><td><a href="https://github.com/kraken-build/kraken-build/pull/44">kraken-build/kraken-build#44</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Breaking change</td><td>

Remove support for hash-comment style build requirements when resuming builds from an existing state.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/45">kraken-build/kraken-build#45</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Move `pytest` dependency into a Poetry dependency group</td><td></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Fix</td><td>

Don't wrap license or copyright holder in quotes</td><td><a href="https://github.com/kraken-build/kraken-build/pull/40">kraken-build/kraken-build#40</a></td><td></td><td>scott@stevenson.io</td></tr>
  <tr><td>Improvement</td><td>

Make better use of logging and hide the logs of creating a virtual environment, upgrading Pip and installing dependencies unless the operations fail.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/45">kraken-build/kraken-build#45</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Breaking change</td><td>

Remove support for specifying Kraken build script requirements in the hash-comment (#) format. Only the `buildscript()` call from `kraken.common` is now supported.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/45">kraken-build/kraken-build#45</a></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.25.0 (2023-06-19)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Feature</td><td>

add `kraken.common.findpython` module which will be used by kraken-wrapper to find an applicable Python version per the interpreter constraint in the buildscript requirements.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/42">kraken-build/kraken-build#42</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Set `DEFAULT_INTERPRETER_CONSTRAINT` to` >=3.10,<3.11`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/42">kraken-build/kraken-build#42</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Now requires explicitly Python 3.10. We can enable Python 3.11 when Dill 0.3.7 is enabled. (See https://github.com/uqfoundation/dill/issues/595)</td><td><a href="https://github.com/kraken-build/kraken-build/pull/42">kraken-build/kraken-build#42</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Set Python version requirement to =3.10</td><td><a href="https://github.com/kraken-build/kraken-build/pull/42">kraken-build/kraken-build#42</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

Add `list-pythons` command and support for finding an appropriate Python interpreter on the current system for creating the Python build environment in the `VenvBuildEnv` manager.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/42">kraken-build/kraken-build#42</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Add support for `KRAKENW_NO_KEYRING` environment varibale</td><td><a href="https://github.com/kraken-build/kraken-build/pull/42">kraken-build/kraken-build#42</a></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.24.3 (2023-06-19)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

Add manifest_path to artifact metadata for Cargo</td><td><a href="https://github.com/kraken-build/kraken-build/pull/41">kraken-build/kraken-build#41</a></td><td></td><td>luke.tomlin@helsing.ai</td></tr>
</table>

## 0.24.2 (2023-06-17)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

Pass `CargoProject.build_env` to `cargoClippy` task</td><td></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.24.1 (2023-06-14)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

Return the tasks created by `cargo_fmt`</td><td><a href="https://github.com/kraken-build/kraken-build/pull/39">kraken-build/kraken-build#39</a></td><td></td><td>nicolas.vizzari@helsing.ai</td></tr>
</table>

## 0.24.0 (2023-06-13)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

Added colorful error handling</td><td><a href="https://github.com/kraken-build/kraken-build/pull/31">kraken-build/kraken-build#31</a></td><td></td><td>chris.cunningham@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Only check the active toolchain if rustup is installed</td><td><a href="https://github.com/kraken-build/kraken-build/pull/38">kraken-build/kraken-build#38</a></td><td></td><td>nicolas.vizzari@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Add PDM python build system support</td><td><a href="https://github.com/kraken-build/kraken-build/pull/33">kraken-build/kraken-build#33</a></td><td></td><td>simone.zandara@helsing.ai</td></tr>
  <tr><td>Tests</td><td>

Force transitive `markdown-it-py` dependency to `<3.0.0` due to Mypy complaining about the newer syntax in Python 3.10 when a newer version of it would otherwise get installed (see https://github.com/python/mypy/issues/12162)</td><td></td><td></td><td>@NiklasRosenstein</td></tr>
</table>

## 0.23.7 (2023-06-08)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

disable default requirement of Rust nightly</td><td><a href="https://github.com/kraken-build/kraken-build/pull/37">kraken-build/kraken-build#37</a></td><td></td><td>james.baker@helsing.ai</td></tr>
</table>

## 0.23.6 (2023-06-08)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Feature</td><td>

can specify ld_library_path for maturin builds</td><td><a href="https://github.com/kraken-build/kraken-build/pull/36">kraken-build/kraken-build#36</a></td><td></td><td>james.baker@helsing.ai</td></tr>
</table>

## 0.23.5 (2023-06-08)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

Re-allow specfiying one or more tasks while also passing the `--all` flag.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/35">kraken-build/kraken-build#35</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Add `-x` and `-X` options to the `krakenw q tree` command</td><td><a href="https://github.com/kraken-build/kraken-build/pull/35">kraken-build/kraken-build#35</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

The `krakenw q tree` command now includes the task status, if any (only relevant with the `--resume` flag or the `-x` or `-X` options, otherwise tasks have no status when the tree is printed)</td><td><a href="https://github.com/kraken-build/kraken-build/pull/35">kraken-build/kraken-build#35</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

Make cargo fmt use the nightly toolchain by default</td><td><a href="https://github.com/kraken-build/kraken-build/pull/34">kraken-build/kraken-build#34</a></td><td></td><td>nicolas.vizzari@helsing.ai</td></tr>
</table>

## 0.23.4 (2023-05-19)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

Upgrade helm dependencies when packaging a chart</td><td><a href="https://github.com/kraken-build/kraken-build/pull/30">kraken-build/kraken-build#30</a></td><td></td><td>callumPearce</td></tr>
</table>

## 0.20.4 (2023-05-18)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Fix</td><td>

Fix the `dist` function which should use the artifact names when copying them to a distribution.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/29">kraken-build/kraken-build#29</a></td><td></td><td>nicolas.trinquier@helsing.ai</td></tr>
</table>

## 0.20.3 (2023-05-17)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

Fix `Property.provides(X)` which should return `True` when a property is typed as `Property[List[X]]`, but did not because of a change in `typeapi` between `0.2.x` and `1.x`. This bug was introduced by https://github.com/kraken-build/kraken-core/pull/11 in version `0.12.0`.</td><td><a href="https://github.com/kraken-build/kraken-build/pull/28">kraken-build/kraken-build#28</a></td><td></td><td>nicolas.trinquier@helsing.ai</td></tr>
</table>

## 0.20.2 (2023-05-17)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

The `kraken query describe` command no longer outputs a description of _all_ tasks in the graph, but only tasks that were explicitly selected on the command-line.</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Tests</td><td>

Add unit test for clarifying the behavior of optional elements in address resolution</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Deprecate the `Project.subproject(load)` &ndash; Instead, a new `Project.subproject(mode)` parameter was added that can be set to `"empty"`, `"execute"` or `"if-exists"`, The `"if-exists"` mode behaves exactly like the `Project.subproject(load=False)` option. A new semantic is introduced with the `"empty"` mode, which creates a sub-project but does not care if the directory associated with the project exists or if a build script exists as the script will not be executed.</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

`TaskGraph.trim()` will now exclude groups from the returned graph if they are empty and if they have no dependencies or all transitive dependencies are also empty groups</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Tests</td><td>

Add a unit test to validate the behaviour of `Context.resolve_tasks()` and the contents of the `TaskGraph` returned by `Context.get_build_graph()`</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Fix</td><td>

Fixed the address selectors that we fall back to if no selectors are specified on the command-line: They were `[":", ":**:"]`, referencing the root projects and all it's sub-projects, when it should really be `[".", "**:"]`, which references the current project and all of it's sub-projects.</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Single-path elements passed as Kraken task-address selectors are now prefixed with `**:` (recursive wildcard) even if the element contains a glob pattern, such as `lint`, `python.*` or `publish?`, making them semantically equivalent to `**:lint`, `**:python.*` and `**:publish?`, respectively.</td><td></td><td><a href="https://github.com/kraken-build/kraken-build/issues/27">kraken-build/kraken-build#27</a></td><td>niklas.rosenstein@helsing.ai</td></tr>
</table>

## 0.20.1 (2023-05-15)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

Move code for `Supplier` from `nr-stream` package to `kraken-common`</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Use `kraken.common.supplier.Supplier` instead of `nr.stream.Supplier`, Remove `kraken.core.api` in favor of `kraken.core`</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
  <tr><td>Improvement</td><td>

Replace imports from `kraken.core.api` with `kraken.core` and imports of `nr.stream.Supplier` with `kraken.common.Supplier`</td><td></td><td></td><td>niklas.rosenstein@helsing.ai</td></tr>
</table>

## 0.20.0 (2023-05-13)

<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>
  <tr><td>Improvement</td><td>

Bump `kraken-core` to `^0.12.4` and `databind.json` to `4.2.5`.</td><td><a href="https://github.com/kraken-build/kraken-std/pull/154">kraken-build/kraken-std#154</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Feature</td><td>

Maturin: adds tooling for cross-compilation using zig</td><td><a href="https://github.com/kraken-build/kraken-std/pull/145">kraken-build/kraken-std#145</a></td><td></td><td>@Tpt</td></tr>
  <tr><td>Fix</td><td>

Poetry: strips '(Activated)' from 'poetry env list --full-path' result</td><td><a href="https://github.com/kraken-build/kraken-std/pull/146">kraken-build/kraken-std#146</a></td><td></td><td>@Tpt</td></tr>
  <tr><td>Fix</td><td>

fix `mypy_stubtest` function name (was: `mypy_subtest`)</td><td><a href="https://github.com/kraken-build/kraken-std/pull/153">kraken-build/kraken-std#153</a></td><td></td><td>@NiklasRosenstein</td></tr>
  <tr><td>Improvement</td><td>

When `git describe` fails, we fall back to `0.0.0-N-gSHA` where `N` is the number of commits on `HEAD`.</td><td></td><td></td><td>@NiklasRosenstein</td></tr>
</table>
<!-- end runcmd -->
