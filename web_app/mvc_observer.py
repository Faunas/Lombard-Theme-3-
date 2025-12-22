# mvc_observer.py
from __future__ import annotations
from typing import Protocol, Any, Iterable, Callable, Dict, List, Tuple


class Observer(Protocol):
    def update(self, event: str, payload: Any) -> None: ...


class Subject:
    def __init__(self) -> None:
        self._observers: list[Observer] = []

    def attach(self, obs: Observer) -> None:
        if obs not in self._observers:
            self._observers.append(obs)

    def detach(self, obs: Observer) -> None:
        if obs in self._observers:
            self._observers.remove(obs)

    def notify(self, event: str, payload: Any) -> None:
        for obs in list(self._observers):
            obs.update(event, payload)
