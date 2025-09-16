from __future__ import annotations

import asyncio
from typing import ClassVar

from clkpoc.df.pairPps import PairPps
from clkpoc.dsc import Dsc
from clkpoc.phaseAligner import PhaseAligner
from clkpoc.TADD import TADD
from clkpoc.tsTypes import PairTs


class PhaseStep:
    """Singleton-like disciplined phase stepper that runs in the background.

    - First instantiation schedules a background asyncio Task and returns immediately.
    - Subsequent instantiations are no-ops while the task is active.
    - When the background task completes, a later instantiation can start a new one.

    First, pulse the ARM pin on the TADD-2 Mini via GPIO to trigger a phase step.
    Then, wait to ignore any PPS pairs from before the phase stepped.
    """

    _task: ClassVar[asyncio.Task[None] | None] = None

    def __init__(self, pairPps: PairPps) -> None:
        # If one is already running, do nothing.
        if PhaseStep._task is not None and not PhaseStep._task.done():
            return

        # Clean up any previous completed task reference and schedule a new one.
        loop = asyncio.get_running_loop()
        PhaseStep._task = loop.create_task(self._run(), name="PhaseStep")
        self.tadd = TADD()
        self.dsc = Dsc()
        PhaseStep._task.add_done_callback(lambda _: setattr(PhaseStep, "_task", None))
        self.pairPps = pairPps
        self.coarseLock = asyncio.Event() # XXX improve naming here
        f0Hz = 10_000_000.0
        hzPerLsb = -4.2034700315e-05   # Hz per code
        self.coarseAlign = PhaseAligner(
            f0Hz=f0Hz,
            hzPerLsb=hzPerLsb,
            codeMin=11400,
            codeMax=15000,
            codeInit=13200,
            tauSec=5.0,          # ~5 s time constant → assertive but controlled
            maxPpb=20.0,         # your VCO pull (ppb)
            goalNs=15.0,         # handoff threshold
            maxCodesPerStep=50,  # slew guard (~2.1 mHz per s with your slope)
            sampleTime=1.0,
            holdCount=2
        )

    async def _run(self) -> None:
        print("PhaseStep pulsing TADD")
        self.tadd.pulse()
        print("PhaseStep starting coarse alignment")
        self.pairPps.pub.sub("pairPps", self.onPairPps)
        await asyncio.sleep(1.0) # XXX maybe unecessary
        # XXX may have to eat first few PairPps events here
        await self.coarseLock.wait()
        print("PhaseStep coarse alignment complete.")

    def onPairPps(self, pair: PairTs) -> None:
        dscDev = pair.gnsTs.refTs.subFrom(pair.dscTs.refTs)
        dscDevSec = dscDev.toPicoseconds()*1e-12
        newVal, done = self.coarseAlign.step(-dscDevSec)
        self.dsc.writeDac(newVal)
        print(f"PhaseStep: dscDev={dscDevSec*1e9:5.1f} newVal={newVal}")
        if not done:
            return
        self.pairPps.pub.unsub("pairPps", self.onPairPps)
        self.coarseLock.set()

    @classmethod
    def is_running(cls) -> bool:
        t = cls._task
        return t is not None and not t.done()

