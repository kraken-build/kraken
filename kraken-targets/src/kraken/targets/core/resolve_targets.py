from dataclasses import dataclass
from typing import Any

from adjudicator import collect_rules, get, rule
from kraken.core import Context
from kraken.core.address import Address
from kraken.core.system.errors import ProjectNotFoundError

from kraken.targets.rulerunner import RuleRunner
from kraken.targets.target import Target, TargetNotFoundError, get_target


@dataclass(frozen=True)
class ResolveTargetsRequest:
    addresses: tuple[Address]
    relative_to: Address | None = None
    transitive: bool = False


@dataclass(frozen=True)
class ResolvedTargets:
    targets: tuple[Target[Any], ...]


class ResolveAddressError(Exception):
    pass


@rule
def resolve_targets(request: ResolveTargetsRequest) -> ResolvedTargets:
    """
    Resolve the given targets.
    """

    context = get(Context)
    results = []

    for address in request.addresses:
        if not address.is_absolute():
            if not request.relative_to:
                raise ValueError(f"Cannot resolve relative address {address!r} without a relative_to address")
            address = request.relative_to.concat(address)
        try:
            project = context.get_project(address.parent)
        except ProjectNotFoundError:
            raise ResolveAddressError(address)
        try:
            results.append(get_target(project, address.name))
        except TargetNotFoundError:
            raise ResolveAddressError(address)

    return ResolvedTargets(tuple(results))


def register(runner: RuleRunner) -> None:
    runner.engine.add_rules(collect_rules())
