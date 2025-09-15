from __future__ import annotations

import asyncio
from typing import ClassVar

from clkpoc.TADD import TADD


class PhaseStep:
    """Singleton-like phase stepper that runs in the background.

    - First instantiation schedules a background asyncio Task and returns immediately.
    - Subsequent instantiations are no-ops while the task is active.
    - When the background task completes, a later instantiation can start a new one.

    For now, the background task simply sleeps for 3 seconds.
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
#        print("PhaseStep started.")

    async def _run(self) -> None:
        print("PhaseStep pulsing TADD...")
        self.tadd.pulse()
        print("PhaseStep waiting to ignore PPS pair after TADD step ...")
        await asyncio.sleep(1.0)
        print("PhaseStep completed.")

    @classmethod
    def is_running(cls) -> bool:
        t = cls._task
        return t is not None and not t.done()

