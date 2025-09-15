import logging
import time
from collections.abc import Callable
from typing import Any


class Publisher:
    """
    Minimal inline publisher:
      - sub(callback) registers a plain function (no async)
      - publish(event) calls each callback in order, inline
      - unsub(callback) removes a subscriber
      - warns if a callback raises or runs too long
    """
    # I'm concerned that warning about slow callback may cause future
    # callbacks to run more slowly, perhaps due to cache misses and
    # downstream consequences of complex system behavior.
    # Watch out for positive feedback on such warnings.
    def __init__(self, name: str, warnIfSlowMs: float | None = None):
        self.name = name
        self.warnIfSlowMs = warnIfSlowMs
        self.subscribers: list[Callable[[Any], None]] = []

    def sub(self, callback: Callable[[Any], None]) -> None:
        if not callable(callback):
            raise TypeError("callback must be callable")
        self.subscribers.append(callback)

    def unsub(self, callback: Callable[[Any], None]) -> None:
        self.subscribers = [cb for cb in self.subscribers if cb is not callback]

    def clear(self) -> None:
        self.subscribers.clear()

    def count(self) -> int:
        return len(self.subscribers)

    def publish(self, event: Any) -> None:
        if not self.subscribers:
            return
        # iterate over a copy so unsub during delivery is safe
        for cb in list(self.subscribers):
            start = time.perf_counter()
            try:
                result = cb(event)
                # detect accidental async def usage
                if hasattr(result, "__await__"):
                    logging.warning(f"{self.name}: subscriber returned coroutine; "
                                    f"callbacks must be sync functions")
            except Exception as e:
                logging.exception(f"{self.name}: subscriber error: {e}")
            else:
                if self.warnIfSlowMs is not None:
                    durMs = (time.perf_counter() - start) * 1000.0
                    if durMs >= self.warnIfSlowMs:
                        logging.warning(
                            f"{self.name}: slow subscriber took {durMs:.1f} ms")
