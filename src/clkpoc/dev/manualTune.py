#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import sys
import termios
from collections import deque
from contextlib import contextmanager

from clkpoc.dev.valueController import ValueController
from clkpoc.df.pairPps import PairPps
from clkpoc.dsc import Dsc
from clkpoc.f9t import F9T
from clkpoc.phaseStep import PhaseStep
from clkpoc.rollingMean import RollingMean
from clkpoc.tic import TIC
from clkpoc.tsTypes import PairTs, Ts

INITIAL_DAC = 13_200


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


async def run_manual_tune() -> None:

    def fitSlopePerSec(ys: list[float]) -> float:
        """Least-squares slope dy/dt using x = 0,1,2,..., ts=1s spacing (then scale by ts)."""
        n = len(ys)
        if n < 2:
            return 0.0
        xMean = (n - 1) / 2.0
        yMean = sum(ys) / float(n)
        sxx = 0.0
        sxy = 0.0
        for i, y in enumerate(ys):
            dx = i - xMean
            dy = y - yMean
            sxx += dx * dx
            sxy += dx * dy
        if sxx == 0.0:
            return 0.0
        slopePerSample = sxy / sxx
        return slopePerSample

    def showTune() -> None:
        nonlocal dscDev, lastDscDev, dac, lastDac, errHist, f0Hz, hzPerLsb
        dscDevNs = dscDev.toPicoseconds() / 1e3
        if lastDscDev is None or dscDev is None:
            dscDevDeltaNs = 0.0
        else:
            dscDevDelta = dscDev - lastDscDev
            dscDevDeltaNs = dscDevDelta.toPicoseconds() / 1e3

        # estimate frequency from LS slope of phase
        if len(errHist) >= 3:
            slope = fitSlopePerSec(list(errHist))   # seconds/second
            freqEstHz = -f0Hz * slope               # Hz
            # compute zero-frequency code from current code and freq estimate
            codeZero = float(dac) - (freqEstHz / hzPerLsb)

        ffePpb = f"FFE {ffePpbRm15:8.3f}" if ffePpbRm15 is not None else "FFE ------"
        print(f"dscDev {dscDevDeltaNs:+5.1f}Δ to {dscDevNs:5.1f}ns, {ffePpb} PPB, "
              f"DAC {dac-lastDac:+5d}Δ to {dac}, "
              f"codeZero {codeZero if 'codeZero' in locals() else 0.0:8.1f}")
        lastDscDev, lastDac = dscDev, dac

    def onNewVal(val: int) -> None:
        nonlocal dac
        dac = val
        showTune()
        if dsc is not None:
            dsc.writeDac(val)

    def onPairPps(pair: PairTs) -> None:
        nonlocal dscDev, lastPair, ffeRm15, ffePpbRm15, errHist
        # Get deviation of Dsc PPS from Gns PPS timestamp on reference timescale
        dscDev = pair.dscTs.refTs - pair.gnsTs.refTs

        errHist.append(dscDev.toPicoseconds()*1e-12)

        # XXX This should be in its own dataflow someday
        if lastPair is not None:
            # Gns time interval since last pair
            gnsTi = pair.gnsTs.refTs-lastPair.gnsTs.refTs
            dscTi = pair.dscTs.refTs-lastPair.dscTs.refTs
            # Get fractional frequency error in parts per billion
            assert gnsTi != 0.0, "Zero gnsTi in onPairPps"
            ffePpb = 1e9*(dscTi-gnsTi)/gnsTi
            ffePpbRm15 = ffeRm15.add(ffePpb)
        lastPair = pair

        showTune()

    def onTrigger() -> None:
        PhaseStep()

    dscDev: Ts | None = None
    lastDscDev: Ts | None = None
    dac: int = INITIAL_DAC
    lastDac: int = INITIAL_DAC
    win: int = 7 # typ 5-9
    errHist: deque[float] = deque(maxlen=win)
    f0Hz: float = 10e6
    hzPerLsb = -4.2034700315e-05   # Hz per code, from measurement
    lastPair: PairTs | None = None
    ffeRm15 = RollingMean(3)  # rolling mean of fractional freq error in ppb
    ffePpbRm15: float | None = None

    loop = asyncio.get_running_loop()
    controller = ValueController(loop, value=dac, on_change=onNewVal, on_trigger=onTrigger)
    dsc = Dsc()

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
