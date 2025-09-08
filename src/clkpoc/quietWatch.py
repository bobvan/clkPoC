import asyncio
import logging
import time


# Log warning if you don't pet the watchdog within warnAfterSec
class QuietWatch:
    def __init__(self, name: str, warnAfterSec: float=2.0):
        self.name = name
        self.warnAfterSec = warnAfterSec
        self.lastReadNs = time.monotonic_ns()
        self.stopEvent = asyncio.Event()

    def pet(self):
        self.lastReadNs = time.monotonic_ns()

    async def run(self):
        warnedForThisSilence = False
        while not self.stopEvent.is_set():
            now = time.monotonic_ns()
            quietSec = (now - self.lastReadNs) / 1e9
            if quietSec >= self.warnAfterSec and not warnedForThisSilence:
                logging.warning(f"{self.name}: no data for {quietSec:.2f}s")
                warnedForThisSilence = True
            if quietSec < self.warnAfterSec:
                warnedForThisSilence = False  # reset once data resumes
            await asyncio.sleep(0.1)

    def stop(self):
        self.stopEvent.set()
