#!/usr/bin/env python

import argparse
import os

from cloudsmith_api import ApiClient, Configuration, ReposApi, UserApi  # type: ignore[import]

CLOUDSMITH_API_KEY = "CLOUDSMITH_API_KEY"

parser = argparse.ArgumentParser()
parser.add_argument("--api-key", help=f"the CloudSmith.io api key; can also be supplied via {CLOUDSMITH_API_KEY}")

subparsers = parser.add_subparsers(dest="cmd")

ls_command = subparsers.add_parser("ls")

rm_command = subparsers.add_parser("rm")
rm_command.add_argument("repos", metavar="repo", nargs="+", help="the repos to delete")
rm_command.add_argument("-f", "--force", action="store_true", help="ignore missing repos")


def main() -> None:
    args = parser.parse_args()
    if not args.cmd:
        parser.print_usage()
        return
    if not args.api_key:
        if CLOUDSMITH_API_KEY in os.environ:
            args.api_key = os.environ[CLOUDSMITH_API_KEY]
        else:
            parser.error("missing option: --api-key")

    config = Configuration()
    config.api_key["X-Api-Key"] = args.api_key
    client = ApiClient(config)
    repos = ReposApi(client)

    if args.cmd == "ls":
        for repo in repos.repos_all_list():
            print(repo.name)
        return

    if args.cmd == "rm":
        has_repos = {r.name: r for r in repos.repos_all_list()}
        if not args.force:
            for repo in args.repos:
                if repo not in has_repos:
                    parser.error(f"repo `{repo}` does not exist")
        for repo in args.repos:
            if repo in has_repos:
                repos.repos_delete(has_repos[repo].namespace, repo)
                print("deleted", repo)
        return

    assert False


if __name__ == "__main__":
    main()
