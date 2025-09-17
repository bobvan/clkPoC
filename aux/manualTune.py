#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import os
import sys
import termios
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List
from clkpoc.f9t import F9T
from clkpoc.tic import TIC
from clkpoc.df.pairPps import PairPps
from clkpoc.phaseStep import PhaseStep
from clkpoc.dsc import Dsc

LOWER_BOUND = 0
UPPER_BOUND = 65_535
INITIAL_VALUE = 13_200


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
    _phaseStep = None # PhaseStep instance created below as needed

    def getValue(self) -> int:
        return self.value

    def start(self) -> None:
        fd = sys.stdin.fileno()
        self.loop.add_reader(fd, self._on_stdin_ready)

    def stop(self) -> None:
        fd = sys.stdin.fileno()
        self.loop.remove_reader(fd)

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

                if ch in (" ", "\t"):
                    _phaseStep = PhaseStep()

                delta = self._delta_map.get(ch)
                if delta is not None:
                    self.value = clamp(self.value + delta)
        finally:
            self.stop()

globalController: ValueController = None # XXX hacky
globalDsc: Dsc = None # XXX hacky

def onPairPps(pair: PairTs) -> None:
    # Get deviation of Dsc PPS from Gns PPS timestamp on reference timescale
    dscDev = pair.dscTs.refTs - pair.gnsTs.refTs
    dscDevNs = dscDev.toPicoseconds()/1e3
    setVal = globalController.getValue()
    print(f"dscDev {dscDevNs:5.1f}ns, value {setVal}")
    globalDsc.writeDac(setVal)

async def run_manual_tune() -> None:
    loop = asyncio.get_running_loop()

    controller = ValueController(loop)
    global globalController # XXX hacky
    globalController = controller

    dsc = Dsc()
    global globalDsc # XXX hacky
    globalDsc = dsc

    f9t = F9T(
        "/dev/serial/by-id/usb-u-blox_AG_-_www.u-blox.com_u-blox_GNSS_receiver-if00", 9600)
    tic = TIC(
        "/dev/serial/by-id/usb-Arduino__www.arduino.cc__0042_95037323535351803130-if00", 115200)
    pairPps = PairPps(tic, "ppsGnsOnRef", "ppsDscOnRef")
    pairPps.pub.sub("pairPps", onPairPps)

    tasks = [
        asyncio.create_task(controller.run(), name="value-controller"),
        asyncio.create_task(f9t.run(), name="f9t"),
        asyncio.create_task(tic.run(), name="tic"),
    ]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    with raw_stdin():
        try:
            asyncio.run(run_manual_tune())
        except KeyboardInterrupt:
            pass
