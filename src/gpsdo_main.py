# gpsdo_main.py
import asyncio, json, logging, time, re
import serial_asyncio as serialAsyncio
from dataclasses import dataclass
from enum import Enum

from f9t import F9T

# third party imports (install as needed)
# import aiosqlite

# XXX next up: Turn on a linter
# XXX next up: Try unplugging F9T and TIC to check error handling
# XXX next up: Time-bounded consideration of watchdog for F9T and TIC
# XXX next up: Initialize F9T to output TIM-TP messages and other required state
# XXX next up: Figure out what @dataclass does
# XXX next up: Define mapping of chA/B to PPS signals
# XXX next up: Define IPC messages for TIM-TP message and TIC timestamps with host time


class Mode(Enum):
    idle = 0
    disciplining = 1
    holdover = 2
    fault = 3


@dataclass
class Event:
    tsMonoNs: int
    source: str
    kind: str
    data: dict


def nowNs():
    return time.monotonic_ns()


class Registry:
    def __init__(self):
        self.mode = Mode.idle
        self.dacCode = 0
        self.lastPpsErrorNs = None
        self.health = {"sat": 0, "f9tOk": False, "ticOk": False}


async def ticReader(eventBus, port, baud, discard_interval=1.0):
    reader, writer = await serialAsyncio.open_serial_connection(url=port, baudrate=baud)
    start_time = asyncio.get_event_loop().time()  # Get the current time
    discarded_lines = 0

    while True:
        raw = await reader.readline()
        line = raw.decode("utf-8").rstrip()

        # Check if we are still within the discard interval
        if asyncio.get_event_loop().time() - start_time < discard_interval:
            discarded_lines += 1
            # XXX log stats here
            continue  # Skip processing this line

        # Process the line after the discard interval
        if not re.fullmatch(r"\d+\.\d{12} ch[AB]", line):
            # XXX log stats here
            continue  # Ignore the line if it doesn't match
        print("got TIC data", line)
        sample = {"ppsErrorNs": 123}  # placeholder
        # await eventBus.put(Event(nowNs(), "tic", "ppsSample", sample))
        # await asyncio.sleep(1.0)


async def dacActor(cmdQueue):
    while True:
        cmd = await cmdQueue.get()
        if cmd["op"] == "setCode":
            code = cmd["code"]
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
    f9t = F9T(eventBus, "/dev/ttyACM1", 9600)
    tasks = [
        asyncio.create_task(f9t.runF9tStream()),
        asyncio.create_task(ticReader(eventBus, "/dev/ttyACM0", 115200)),
        asyncio.create_task(controlLoop(eventBus, reg, dacQueue)),
        asyncio.create_task(dacActor(dacQueue)),
        asyncio.create_task(storageWriter(storageTap)),
        asyncio.create_task(ipcServer(reg, dacQueue)),
        asyncio.create_task(tee()),
    ]
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
