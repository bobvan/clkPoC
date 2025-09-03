# gpsdo_main.py
import asyncio, json, logging, time
from dataclasses import dataclass
from enum import Enum

# third party imports (install as needed)
# import serial_asyncio
# from pyubx2 import UBXReader
# import aiosqlite

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

async def f9tReader(eventBus, port, baud):
    # reader, writer = await serial_asyncio.open_serial_connection(url=port, baudrate=baud)
    while True:
        # raw = await reader.read(4096)
        # for msg in UBXReader.parse(raw):
        #     await eventBus.put(Event(nowNs(), "f9t", "ubx", {"cls": msg.identity, "payload": msg.payload}))
        await asyncio.sleep(1.0)  # placeholder tick
        await eventBus.put(Event(nowNs(), "f9t", "heartbeat", {}))

async def ticReader(eventBus, port, baud):
    while True:
        # parse a PPS phase sample from the TIC stream
        sample = {"ppsErrorNs": 123}  # placeholder
        await eventBus.put(Event(nowNs(), "tic", "ppsSample", sample))
        await asyncio.sleep(1.0)

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
        logging.info(json.dumps({"ts": ev.tsMonoNs, "src": ev.source, "kind": ev.kind, "data": ev.data}))
        eventBus.task_done()

async def ipcServer(reg, dacQueue, path="/tmp/gpsdo.sock"):
    async def handle(reader, writer):
        try:
            raw = await reader.readline()
            req = json.loads(raw.decode())
            if req.get("cmd") == "getState":
                resp = {"mode": reg.mode.name, "dacCode": reg.dacCode, "lastPpsErrorNs": reg.lastPpsErrorNs, "health": reg.health}
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
    tasks = [
        asyncio.create_task(f9tReader(eventBus, "/dev/ttyACM0", 115200)),
        asyncio.create_task(ticReader(eventBus, "/dev/ttyUSB0", 115200)),
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
