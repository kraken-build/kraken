import importlib
from typing import Any, Callable, Iterable

from adjudicator import Params, RulesEngine

from kraken.targets.goal import Goal
from kraken.targets.subtypes import SubtypesRegistry


class RuleRunner:
    def __init__(self, modules: Iterable[str] = ()) -> None:
        self.engine = RulesEngine([])
        self.subtypes = SubtypesRegistry()
        self.load(*modules)

    def load(self, *modules: str) -> None:
        """
        Populate the RuleRunner with the rules and subtypes from the specified modules by calling
        their `register()` functions. The functions should receive the RuleRunner as a positional
        argument and register their rules and subtypes with it.
        """

        for module in modules:
            mod = importlib.import_module(module)
            register: Callable[[RuleRunner], None] = getattr(mod, "register")
            register(self)

    def run(self, goal: type[Goal]) -> Goal:
        with self.engine.as_current():
            subsystem = goal.subsystem_cls()
            return self.engine.get(goal, Params([subsystem]))

    def get(self, type_: type[Any], params: Params.InitType) -> Any:
        with self.engine.as_current():
            return self.engine.get(type_, Params(params))
