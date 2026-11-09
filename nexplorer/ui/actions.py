"""Shared actions: each is defined once and used by the menu bar, its shortcut, the context
menus and (later) the toolbar. An action has a label, a shortcut and, for each side (Local or
Next), a binding: when it is enabled and what it does. It applies to the active pane; a side
without a binding greys the action while that pane is active."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QKeySequence

LOCAL, NEXT = "local", "next"


@dataclass(frozen=True)
class Binding:
    """What an action does on one side."""

    enabled: Callable[[], bool]
    run: Callable[[], None]


class SharedActions(QObject):
    def __init__(self, parent: QObject, active_side: Callable[[], str]):
        super().__init__(parent)
        self._active_side = active_side
        self._actions: dict[str, QAction] = {}
        self._bindings: dict[str, dict[str, Binding]] = {}

    def define(
        self,
        key: str,
        label: str,
        shortcut: str = "",
        *,
        local: Binding | None = None,
        next: Binding | None = None,
        both: Binding | None = None,
        checkable: bool = False,
    ) -> QAction:
        """Create the action `key`. `both` is a binding for the two sides (a global action)."""
        action = QAction(label, self.parent())
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.setCheckable(checkable)
        action.triggered.connect(lambda _checked=False, k=key: self._trigger(k))
        self._actions[key] = action
        self._bindings[key] = {}
        for side, binding in ((LOCAL, local or both), (NEXT, next or both)):
            if binding is not None:
                self.bind(key, side, binding)
        action.setEnabled(False)
        return action

    def bind(self, key: str, side: str, binding: Binding) -> None:
        """Give the action `key` its behaviour on `side` (a side can be added after `define`)."""
        self._bindings[key][side] = binding

    def action(self, key: str) -> QAction:
        return self._actions[key]

    def refresh(self) -> None:
        """Grey or enable every action for the active pane."""
        side = self._active_side()
        for key, action in self._actions.items():
            binding = self._bindings[key].get(side)
            action.setEnabled(binding is not None and binding.enabled())

    def _trigger(self, key: str) -> None:
        binding = self._bindings[key].get(self._active_side())
        if binding is not None and binding.enabled():
            binding.run()
