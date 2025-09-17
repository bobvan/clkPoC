from __future__ import annotations

import asyncio
import os
import sys
import termios
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List

LOWER_BOUND = 0
UPPER_BOUND = 65_535
INITIAL_VALUE = 32_767


def clamp(value: int) -> int:
    return max(LOWER_BOUND, min(UPPER_BOUND, value))


def build_delta_map() -> Dict[str, int]:
    pairs = [
        (-1, {"f", "g", "r", "t", "v", "b"}),
        (-10, {"d", "e", "c"}),
        (-100, {"s", "w", "x"}),
        (-1000, {"a", "q", "z"}),
        (1, {"h", "j", "y", "u", "n", "m"}),
        (10, {"k", "i", ","}),
        (100, {"l", "o", "."}),
        (1000, {"p", ";", "/"}),
    ]
    mapping: Dict[str, int] = {}
    for amount, keys in pairs:
        for key in keys:
            mapping[key] = amount
            mapping[key.upper()] = amount
    return mapping


@contextmanager
def raw_stdin() -> None:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] &= ~(termios.ECHO | termios.ICANON)
    termios.tcsetattr(fd, termios.TCSADRAIN, new)
    try:
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print()  # keep shell prompt tidy


@dataclass
class ValueController:
    loop: asyncio.AbstractEventLoop
    value: int = INITIAL_VALUE
    _digits: List[str] = field(default_factory=list)
    _delta_map: Dict[str, int] = field(default_factory=build_delta_map)
    _queue: asyncio.Queue[str] = field(default_factory=asyncio.Queue)
    _printing_task: asyncio.Task[None] | None = None

    def start(self) -> None:
        fd = sys.stdin.fileno()
        self.loop.add_reader(fd, self._on_stdin_ready)

    def stop(self) -> None:
        fd = sys.stdin.fileno()
        self.loop.remove_reader(fd)
        if self._printing_task and not self._printing_task.done():
            self._printing_task.cancel()

    def _on_stdin_ready(self) -> None:
        ch = os.read(sys.stdin.fileno(), 1)
        if ch:
            self._queue.put_nowait(ch.decode(errors="ignore"))

    async def _printer(self) -> None:
        try:
            while True:
                print(self.value)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    async def run(self) -> None:
        self.start()
        self._printing_task = asyncio.create_task(self._printer())
        try:
            while True:
                ch = await self._queue.get()
                if ch in ("\x03", "\x04"):  # Ctrl+C, Ctrl+D
                    raise asyncio.CancelledError
                if ch.isdigit():
                    self._digits.append(ch)
                    continue

                if self._digits:
                    self.value = clamp(int("".join(self._digits)))
                    self._digits.clear()

                if ch in ("\r", "\n"):
                    continue

                delta = self._delta_map.get(ch)
                if delta is not None:
                    self.value = clamp(self.value + delta)
        finally:
            self.stop()


async def main() -> None:
    controller = ValueController(asyncio.get_running_loop())
    try:
        async with asyncio.timeout(None):  # handy place to add global timeout if desired
            await controller.run()
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    with raw_stdin():
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            pass
