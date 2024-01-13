from collections.abc import Sequence
import logging

from more_itertools import flatten
from importlib_metadata import entry_points  # Stdlib module is bugged in 3.10
from kraken.core.system.project import Project
from kraken.core.system.target import NamedTarget, T_Target
from .goals import InstallGoal, BuildGoal, RunGoal
from adjudicator import RuleEngine, collect_rules, rule, union_rule, Params, get

__all__ = [
    "resolve_dependencies",
    "InstallGoal",
    "BuildGoal",
    "RunGoal",
    "get",
    "rule",
    "union_rule",
]

logger = logging.getLogger(__name__)


def build_rule_engine() -> RuleEngine:
    from kraken.core import Project, Address
    from pathlib import Path

    module_names = [ep.value for ep in entry_points(group="kraken.build.experimental.rules")]
    engine = RuleEngine(flatten([collect_rules(module_name) for module_name in module_names]))
    engine.hashsupport.register(Project, lambda project: engine.hashsupport(project.address))
    engine.hashsupport.register(Address, lambda address: engine.hashsupport((address.is_absolute(), address._elements)))
    engine.hashsupport.register(Path, lambda path: engine.hashsupport((type(path), str(path))))
    return engine


def resolve_dependencies(project: Project, dependencies: Sequence[str], target_type: type[T_Target]) -> list[T_Target]:
    """
    Resolve a list of dependencies to a list of targets of a specific type.
    """

    logger.debug("resolve_dependencies(%r, %r, %r)", project, dependencies, target_type)

    # TODO: How to do 1:N resolution? E.g. a rule that takes a single of the input types and produces multiple
    #       of the output types?

    # Resolve the immediate dependencies.
    results = []
    targets = project.context.resolve_tasks(dependencies, relative_to=project, object_type=NamedTarget)
    if not targets:
        raise ValueError(f"no targets found for dependency {dependencies!r}")
    for target in [tgt.data for tgt in targets]:
        # TODO: Move identity rule into adjudicator module.
        # TODO: Catch when no applicable rule is found.
        # TODO: Gracefully catch errors to provide a comprehensive stack trace.
        if isinstance(target, target_type):
            result = target
        else:
            result = project.context.rule_engine.get(target_type, Params(target))
        results.append(result)

    return results
