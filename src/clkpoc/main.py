# pyright: basic
import asyncio
import json
import logging
import time
from enum import Enum

from clkpoc.df.pairPps import PairPps
from clkpoc.dfPpsCsvLog import PpsCsvLog
from clkpoc.f9t import F9T
from clkpoc.phaseWatch import PhaseWatch
from clkpoc.tic import TIC

# third party imports (install as needed)
# import aiosqlite

# XXX next up: Move tests/testTs.py to aux/
# XXX next up: Move clkTypes.py to aux/
# XXX next up: Move publisher.py to aux/

# XXX next up: Move dfPpsCsvLog to df/

# XXX next up: Add types from ts_types.py to tsn.py
# XXX next up: Move ts_types.py to aux/

# XXX next up: Rename Tsn to Ts
# XXX next up: Rename tests from Tsn to Ts
# XXX next up: Rename tsn.py to tsTypes.py
# XXX next up: Final Tsn search/cleanup

# XXX next up: Implement DAC I2C writes (with asyncio.to_thread) and integrate into control loop
# XXX next up: Initialize F9T to output TIM-TP messages and other required state
# XXX next up: Define IPC messages for TIM-TP message and TIC timestamps with host time
# XXX next up: Clean up main.py and enable strict type checking


class Mode(Enum):
    idle = 0
    disciplining = 1
    holdover = 2
    fault = 3


def nowNs():
    return time.monotonic_ns()


class Registry:
    def __init__(self):
        self.mode = Mode.idle
        self.dacCode = 0
        self.lastPpsErrorNs = None
        self.health = {"sat": 0, "f9tOk": False, "ticOk": False}


async def dacActor(cmdQueue):
    while True:
        cmd = await cmdQueue.get()
        if cmd["op"] == "setCode":
            pass
            # code = cmd["code"]
            # blocking i2c write wrapped in to_thread(...)
            # await asyncio.to_thread(write_dac, code)
        cmdQueue.task_done()


async def controlLoop(eventBus, reg, dacQueue):
    kp = 0.1
    ki = 0.02
    integ = 0.0
    while True:
        ev = await eventBus.get()
        if ev.kind == "ppsSample":
            err = ev.data["ppsErrorNs"]
            reg.lastPpsErrorNs = err
            # simple PI loop (replace with your preferred filter)
            integ += err
            delta = kp * err + ki * integ
            newCode = max(0, min(65535, int(reg.dacCode - delta)))
            if newCode != reg.dacCode:
                reg.dacCode = newCode
                await dacQueue.put({"op": "setCode", "code": newCode})
        eventBus.task_done()


async def storageWriter(eventBus):
    # db = await aiosqlite.connect("gpsdo.db")
    # await db.execute("pragma journal_mode=wal;")
    while True:
        ev = await eventBus.get()
        # await db.execute("insert into events values (?, ?, ?, ?, ?)",
        #                  (ev.tsMonoNs, None, ev.source, ev.kind, json.dumps(ev.data)))
        # await db.commit()
        logging.info(
            json.dumps(
                {"ts": ev.tsMonoNs, "src": ev.source, "kind": ev.kind, "data": ev.data}
            )
        )
        eventBus.task_done()


async def ipcServer(reg, dacQueue, path="/tmp/gpsdo.sock"):
    async def handle(reader, writer):
        try:
            raw = await reader.readline()
            req = json.loads(raw.decode())
            if req.get("cmd") == "getState":
                resp = {
                    "mode": reg.mode.name,
                    "dacCode": reg.dacCode,
                    "lastPpsErrorNs": reg.lastPpsErrorNs,
                    "health": reg.health,
                }
                writer.write((json.dumps(resp) + "\n").encode())
            elif req.get("cmd") == "setDac":
                await dacQueue.put({"op": "setCode", "code": int(req["code"])})
                writer.write(b'{"ok":true}\n')
            else:
                writer.write(b'{"error":"unknown"}\n')
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_unix_server(handle, path=path)
    async with server:
        await server.serve_forever()


async def main():
    logging.basicConfig(level=logging.INFO)
    reg = Registry()
    eventBus = asyncio.Queue(maxsize=1000)
    storageTap = asyncio.Queue(maxsize=2000)  # tee to storage

    # tee: every event also goes to storageWriter
    async def tee():
        while True:
            ev = await eventBus.get()
            # fan out: controlLoop consumes directly; we also push to storageTap
            await storageTap.put(ev)
            eventBus.task_done()

    dacQueue = asyncio.Queue()
    f9t = F9T(eventBus,
        "/dev/serial/by-id/usb-u-blox_AG_-_www.u-blox.com_u-blox_GNSS_receiver-if00", 9600)
    tic = TIC(eventBus,
        "/dev/serial/by-id/usb-Arduino__www.arduino.cc__0042_95037323535351803130-if00", 115200)
    PpsCsvLog(tic, "ppsGnsOnRef", "ppsGns.csv")
    PpsCsvLog(tic, "ppsDscOnRef", "ppsDsc.csv")
    pairPps = PairPps(tic, "ppsGnsOnRef", "ppsDscOnRef")
    # Watch for step changes between GNSS and disciplined ref timestamps
    PhaseWatch(pairPps)  # use default threshold; adjust as needed
    tasks = [
        asyncio.create_task(f9t.run()),
        asyncio.create_task(tic.run()),
        asyncio.create_task(controlLoop(eventBus, reg, dacQueue)),
        asyncio.create_task(dacActor(dacQueue)),
        asyncio.create_task(storageWriter(storageTap)),
        asyncio.create_task(ipcServer(reg, dacQueue)),
        asyncio.create_task(tee()),
    ]
    print("main: All async tasks started")
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
