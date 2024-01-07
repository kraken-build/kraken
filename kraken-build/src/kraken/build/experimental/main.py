import argparse
import logging
from pathlib import Path
import sys

from adjudicator import NoMatchingRulesError
from kraken.build.experimental.rules.goals import BuildGoal, InstallGoal

from kraken.core import Context

from kraken.build.experimental.rules import RunGoal, get
from kraken.core.system.target import NamedTarget, Target

logger = logging.getLogger(__name__)
goals = {
    "install": InstallGoal,
    "build": BuildGoal,
    "run": RunGoal,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("goal", choices=goals.keys())
    parser.add_argument("target", help="The target to apply the goal to.")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(levelname)s %(name)s] %(message)s",
    )

    if not args.goal:
        parser.print_help()
        sys.exit(1)

    context = Context(Path.cwd() / ".build")
    with context.as_current():
        context.load_project(Path.cwd())

        goal_type = goals[args.goal]
        matched: set[NamedTarget[Target]] = set()
        for target in context.resolve_tasks(args.target, object_type=NamedTarget):
            try:
                # TODO: Adjudicator feature to plan before executing rules, allowing us to inform
                #       the user when a rule matched before executing it.
                logger.debug("Attempt get(%s, %s)", goal_type.__name__, type(target.data).__name__)
                get(goal_type, target.data)
            except NoMatchingRulesError:
                logger.debug("no matching rules for target: %s", target.name, exc_info=True)
            else:
                matched.add(target)
