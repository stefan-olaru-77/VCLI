"""Command registry powering the command palette and shortcut aliases."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class Command:
    id: str
    title: str
    category: str
    run: Callable[[], None]
    keys: str = ""
    enabled: Callable[[], bool] = field(default=lambda: True)

    @property
    def key(self) -> str:
        return self.title


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(
        self,
        command_id: str,
        title: str,
        category: str,
        run: Callable[[], None],
        keys: str = "",
        enabled: Callable[[], bool] | None = None,
    ) -> Command:
        command = Command(
            id=command_id,
            title=title,
            category=category,
            run=run,
            keys=keys,
            enabled=enabled or (lambda: True),
        )
        self._commands[command_id] = command
        return command

    def get(self, command_id: str) -> Command | None:
        return self._commands.get(command_id)

    def run(self, command_id: str) -> None:
        command = self._commands.get(command_id)
        if command is not None and command.enabled():
            command.run()

    def all(self) -> list[Command]:
        return sorted(
            (command for command in self._commands.values() if command.enabled()),
            key=lambda command: (command.category, command.title.lower()),
        )

    def __len__(self) -> int:
        return len(self._commands)
