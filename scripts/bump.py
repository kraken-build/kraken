#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "tomli",
#     "tomli-w",
# ]
# ///

import argparse
import re
import subprocess
import sys
from datetime import date
from os import fspath
from pathlib import Path

import tomli
import tomli_w

patterns = [
    ("kraken-build/src/kraken/core/__init__.py", r'^__version__ = "(.*?)"$'),
    ("kraken-wrapper/src/kraken/wrapper/__init__.py", r'^__version__ = "(.*?)"$'),
    ("kraken-build/pyproject.toml", r'^version = "(.*?)"$'),
    ("kraken-wrapper/pyproject.toml", r'^version = "(.*?)"$'),
    ("kraken-wrapper/pyproject.toml", r'^\s*"kraken-build==(.*?)",$'),
]

post_bump_hooks = [
    ("kraken-build", "uv lock", ["uv.lock"]),
    ("kraken-wrapper", "uv lock", ["uv.lock"]),
]


def git_add(*paths: str | Path) -> None:
    subprocess.check_call(["git", "add", *(fspath(p) for p in paths)])


def git_commit(message: str) -> None:
    subprocess.check_call(["git", "commit", "-m", message])


def git_tag(name: str, *, force: bool = False) -> None:
    subprocess.check_call(["git", "tag", name, *(["-f"] if force else [])])


def git_push(*refs: str, remote: str = "origin", force: bool = False) -> None:
    subprocess.check_call(["git", "push", remote, *refs, *(["-f"] if force else [])])


def update_files(version: str) -> None:
    def repl(m: re.Match[str]) -> str:
        return m.group(0).replace(m.group(1), version)

    matched_all_patterns = True
    for filename, pattern in patterns:
        path = Path(filename)
        content = path.read_text()
        if not re.search(pattern, content, re.M):
            matched_all_patterns = False
            print(f"error: pattern {pattern} not matched in {filename}")
        else:
            path.write_text(re.sub(pattern, repl, content, 0, re.M))
            print(f"updated {filename}")
            git_add(filename)

    if not matched_all_patterns:
        sys.exit(1)


def run_post_hooks() -> None:
    for cwd, command, stage_files in post_bump_hooks:
        if subprocess.call(command, shell=True, cwd=cwd) != 0:
            sys.exit(1)
        git_add(*[Path(cwd) / f for f in stage_files])


def release_changelog(version: str) -> None:
    unreleased = Path(".changelog/_unreleased.toml")
    if not unreleased.exists():
        return

    data = tomli.loads(unreleased.read_text())
    data["release-date"] = str(date.today())

    released = Path(f".changelog/{version}.toml")
    released.write_text(tomli_w.dumps(data))

    unreleased.unlink()
    print(f"{unreleased} → {released}")
    git_add(unreleased, released)


def create_github_release(version: str) -> None:
    subprocess.check_call(["gh", "release", "create", f"{version}", "--generate-notes"])
    print(f"Created GitHub release v{version}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    parser.add_argument("--release", action="store_true", help="Commit, tag and push.")
    parser.add_argument("--force", action="store_true", help="Force tag and push.")
    args = parser.parse_args()

    update_files(args.version)
    run_post_hooks()
    release_changelog(args.version)
    if args.release:
        git_commit(f"release v{args.version}")
        git_tag(args.version, force=args.force)
        git_push(args.version, force=args.force)
        create_github_release(args.version)


if __name__ == "__main__":
    main()
