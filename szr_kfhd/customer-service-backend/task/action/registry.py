# task/action/registry.py

from task.action.base import Action

class ActionRegistry:
    """ Action注册表 """

    def __init__(self)->None:
        self._actions: dict[str, Action] = {}

    def register(self, action: Action) -> None:
        self._actions[action.name] = action

    def get(self, name: str) -> Action:
        if name not in self._actions:
            raise KeyError(f"Unknown action '{name}'.")
        return self._actions[name]

