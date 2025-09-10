import logging
import time
from collections.abc import Callable
from typing import Any


class TopicPublisher:
    """
    Minimal inline publisher with topic support:
      - sub(topic, callback) registers a plain function (no async) for a topic
      - publish(topic, event) calls each callback for the topic in order, inline
      - unsub(topic, callback) removes a subscriber from a topic
      - clear(topic) clears all subscribers for a topic
      - count(topic) returns the number of subscribers for a topic
      - warns if a callback raises or runs too long
    """
    # I'm concerned that warning about slow callback may cause future
    # callbacks to run more slowly, perhaps due to cache misses and
    # downstream consequences of complex system behavior.
    # Watch out for positive feedback on such warnings.
    def __init__(self, name: str, warnIfSlowMs: float | None = None):
        self.name = name
        self.warnIfSlowMs = warnIfSlowMs
        self.subscribers: dict[str, list[Callable[[Any], None]]] = {}

    def sub(self, topic: str, callback: Callable[[Any], None]) -> None:
        if not callable(callback):
            raise TypeError("callback must be callable")
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)

    def unsub(self, topic: str, callback: Callable[[Any], None]) -> None:
        if topic in self.subscribers:
            self.subscribers[topic] = [cb for cb in self.subscribers[topic] if cb is not callback]
            if not self.subscribers[topic]:  # Remove topic if no subscribers remain
                del self.subscribers[topic]

    def clear(self, topic: str) -> None:
        if topic in self.subscribers:
            del self.subscribers[topic]

    def count(self, topic: str) -> int:
        return len(self.subscribers.get(topic, []))

    def publish(self, topic: str, event: Any) -> None:
        if topic not in self.subscribers or not self.subscribers[topic]:
            return
        # iterate over a copy so unsub during delivery is safe
        for cb in list(self.subscribers[topic]):
            start = time.perf_counter()
            try:
                result = cb(event)
                # detect accidental async def usage
                if hasattr(result, "__await__"):
                    logging.warning(
                        f"{self.name}: subscriber for topic '{topic}' returned coroutine; "
                        f"callbacks must be sync functions")
            except Exception as e:
                logging.exception(f"{self.name}: subscriber error for topic '{topic}': {e}")
            else:
                elapsed = (time.perf_counter() - start) * 1000
                if self.warnIfSlowMs is not None and elapsed > self.warnIfSlowMs:
                    logging.warning(
                        f"{self.name}: subscriber for topic '{topic}' took {elapsed:.2f}ms")


# Example usage:
#if __name__ == "__main__":
#    pub = Publisher("ExamplePublisher", warnIfSlowMs=100)
#
#    def callback1(event):
#        print(f"Callback 1 received: {event}")
#
#    def callback2(event):
#        print(f"Callback 2 received: {event}")
#
#    pub.sub("topic1", callback1)
#    pub.sub("topic1", callback2)
#    pub.publish("topic1", "Hello, Topic 1!")
#
#    pub.unsub("topic1", callback1)
#    pub.publish("topic1", "Hello again, Topic 1!")
#
#    pub.clear("topic1")
#    pub.publish("topic1", "This will not be received.")
