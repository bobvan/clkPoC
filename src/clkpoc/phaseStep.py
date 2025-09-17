from __future__ import annotations

import asyncio
from typing import ClassVar

from clkpoc.TADD import TADD


class PhaseStep:
    """Singleton-like disciplined phase stepper that runs in the background.

    - First instantiation schedules a background asyncio Task and returns immediately.
    - Subsequent instantiations are no-ops while the task is active.
    - When the background task completes, a later instantiation can start a new one.

    First, pulse the ARM pin on the TADD-2 Mini via GPIO to trigger a phase step.
    Then, wait to ignore any PPS pairs from before the phase stepped.
    """

    _task: ClassVar[asyncio.Task[None] | None] = None

    def __init__(self) -> None:
        # If one is already running, do nothing.
        if PhaseStep._task is not None and not PhaseStep._task.done():
            return

        # Clean up any previous completed task reference and schedule a new one.
        loop = asyncio.get_running_loop()
        PhaseStep._task = loop.create_task(self._run(), name="PhaseStep")
        self.tadd = TADD()
        PhaseStep._task.add_done_callback(lambda _: setattr(PhaseStep, "_task", None))


    async def _run(self) -> None:
        print("PhaseStep pulsing TADD")
        self.tadd.pulse()
        print("PhaseStep starting coarse alignment")
        await asyncio.sleep(1.0) # XXX maybe unecessary
        print("PhaseStep coarse alignment complete.")

    @classmethod
    def is_running(cls) -> bool:
        t = cls._task
        return t is not None and not t.done()

