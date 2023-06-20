from kraken.targets.goal import Goal, GoalSubsystem


class InstallGoalSubsystem(GoalSubsystem):
    name = "install"
    help = "Install the project."


class InstallGoal(Goal):
    pass
