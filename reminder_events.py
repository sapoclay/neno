"""Simple observer helpers to keep reminder UIs in sync."""
from __future__ import annotations

import threading
from typing import Callable, Iterable

_listener_lock = threading.Lock()
_listeners: set[Callable[[], None]] = set()

def register_reminders_listener(callback: Callable[[], None]) -> Callable[[], None]:
    """Register a callback fired when reminders list changes.

    Returns a function that can be called to unregister the listener.
    """
    if not callable(callback):
        raise TypeError("callback must be callable")
    with _listener_lock:
        _listeners.add(callback)

    def unregister() -> None:
        with _listener_lock:
            _listeners.discard(callback)

    return unregister

def notify_reminders_updated() -> None:
    """Invoke every registered listener, ignoring individual failures."""
    with _listener_lock:
        current: Iterable[Callable[[], None]] = tuple(_listeners)
    for listener in current:
        try:
            listener()
        except Exception as exc:
            print(f"Error notificando actualización de recordatorios: {exc}")
