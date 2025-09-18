# pyright: basic
import asyncio
import json
import logging

from clkpoc.df.pairPps import PairPps
from clkpoc.df.pairQerr import PairQerr
from clkpoc.df.phaseTrack import PhaseTrack
from clkpoc.df.ppsCsvLog import PpsCsvLog
from clkpoc.f9t import F9T
from clkpoc.phaseWatch import PhaseWatch
from clkpoc.state import State
from clkpoc.tic import TIC

# third party imports (install as needed)
# import aiosqlite

# XXX next up: Move phaseWatch.py to df/phaseWatch.py
# XXX next up: Implement DAC I2C writes (with asyncio.to_thread) and integrate into control loop
# XXX next up: Initialize F9T to output TIM-TP messages and other required state
# XXX next up: Define IPC messages for TIM-TP message and TIC timestamps with host time
# XXX next up: Clean up main.py and enable strict type checking


async def dacActor(cmdQueue):
    while True:
        cmd = await cmdQueue.get()
        if cmd["op"] == "setCode":
            pass
            # code = cmd["code"]
            # blocking i2c write wrapped in to_thread(...)
            # await asyncio.to_thread(write_dac, code)
        cmdQueue.task_done()


#async def phaseTrack(eventBus, state, dacQueue):
#    kp = 0.1
#    ki = 0.02
#    integ = 0.0
#    while True:
#        ev = await eventBus.get()
#        if ev.kind == "ppsSample":
#            err = ev.data["ppsErrorNs"]
#            state.lastPpsErrorNs = err
#            # simple PI loop (replace with your preferred filter)
#            integ += err
#            delta = kp * err + ki * integ
#            newCode = max(0, min(65535, int(state.dacVal - delta)))
#            if newCode != state.dacVal:
#                state.dacVal = newCode
#                await dacQueue.put({"op": "setCode", "code": newCode})
#        eventBus.task_done()


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


async def ipcServer(state, dacQueue, path="/tmp/gpsdo.sock"):
    async def handle(reader, writer):
        try:
            raw = await reader.readline()
            req = json.loads(raw.decode())
            if req.get("cmd") == "getState":
                resp = {
                    "mode": state.mode.name,
                    "dacVal": state.dacVal,
                    "lastPpsErrorNs": state.lastPpsErrorNs,
                    "health": state.health,
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
    state = State()
    eventBus = asyncio.Queue(maxsize=1000)
    storageTap = asyncio.Queue(maxsize=2000)  # tee to storage

    # tee: every event also goes to storageWriter
    async def tee():
        while True:
            ev = await eventBus.get()
            # fan out: phaseTrack consumes directly; we also push to storageTap
            await storageTap.put(ev)
            eventBus.task_done()

    dacQueue = asyncio.Queue()
    state = State()
    f9t = F9T(
        "/dev/serial/by-id/usb-u-blox_AG_-_www.u-blox.com_u-blox_GNSS_receiver-if00", 9600)
    tic = TIC(
        "/dev/serial/by-id/usb-Arduino__www.arduino.cc__0042_95037323535351803130-if00", 115200)
    PpsCsvLog(tic, "ppsGnsOnRef", "ppsGns.csv")
    PpsCsvLog(tic, "ppsDscOnRef", "ppsDsc.csv")
    pairPps = PairPps(tic, "ppsGnsOnRef", "ppsDscOnRef")
    pairQerr = PairQerr(pairPps, f9t, "pairPps", "TIM-TP")  # noqa: F841
    # Watch for step changes between GNSS and disciplined ref timestamps
    PhaseWatch(pairQerr, state)  # use default threshold; adjust as needed
    PhaseTrack(pairPps, state)
    tasks = [
        asyncio.create_task(f9t.run()),
        asyncio.create_task(tic.run()),
#        asyncio.create_task(phaseTrack(eventBus, state, dacQueue)),
        asyncio.create_task(dacActor(dacQueue)),
        asyncio.create_task(storageWriter(storageTap)),
        asyncio.create_task(ipcServer(state, dacQueue)),
        asyncio.create_task(tee()),
    ]
    print("main: All async tasks started")
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
