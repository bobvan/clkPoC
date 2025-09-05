# gpsdo_main.py
import asyncio
import contextlib
import json
import logging
import re
import termios
import time
from dataclasses import dataclass
from enum import Enum

import serial_asyncio as serialAsyncio

from f9t import F9T
from quietWatch import QuietWatch

# third party imports (install as needed)
# import aiosqlite

# XXX next up: Move TIC open code to a class like F9T
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



class TicState(Enum): # XXX This should be a state variable for debug inspection
    startup = 0 # We are ready to send a character to get the config menu
    config1 = 1 # Have sent character, waiting for the "choose one:" prompt
    config2 = 2 # Have sent reset, waiting for 2nd "choose one:" prompt
    stamping = 3 # Have written config changes and are now timestamping

async def ticReader(eventBus, port, baud, discard_interval=1.0):
    reader, writer = await serialAsyncio.open_serial_connection(url=port, baudrate=baud)
    transport = writer.transport

    # If the last guy to open the TIC's serial port didn't set HUPCL, we may see
    # garbeled output at first, then timestamps continuing from the previous run.
    # To avoid that when we're done, we want to leave it in a reset state for our
    # next open, so we set HUPCL if it's not set.
    #
    # Pause callbacks while we tweak termios
    transport.pause_reading()
    try:
        serialObj = (transport.get_extra_info("serial")
                  or getattr(transport, "serial", None))
        fd = serialObj.fileno()
        attrs = termios.tcgetattr(fd)
        cflag = attrs[2]
        if not cflag & termios.HUPCL:
            # HUPCL was not set, so set it now and re-open the serial port
            cflag |= termios.HUPCL
            attrs[2] = cflag
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()   # Python 3.8+; waits for transport shutdown
            await asyncio.sleep(0.1)
            # Re-open serial connection, now with HUPCL for next time we open it
            reader, writer = await serialAsyncio.open_serial_connection(url=port,
                baudrate=baud)

    finally:
        transport.resume_reading()

    # Opening the port this way means the TIC is always in its startup state.
    # We run through the config menu to quickly reset it to all defaults and start
    # timestamping quickly.
    ticState = TicState.startup

    dog = QuietWatch(name=port, warnAfterSec=10)
    dogTask = asyncio.create_task(dog.run())

    try:
        while True:
            raw = await reader.readline()
            # XXX this would be the spot to catch SerialException when TIC is unplugged
            line = raw.decode("utf-8").rstrip()
            if not line:
                continue
            if (ticState == TicState.startup
            and re.fullmatch(r"# Type any character for config menu", line)):
                writer.write(b'x')
                ticState = TicState.config1
            if re.fullmatch(r"choose one:", line):
                if ticState==TicState.config1:
                    writer.write(b'r')
                    ticState = TicState.config2
                elif ticState==TicState.config2:
                    writer.write(b'w')
                    ticState = TicState.stamping
            if ticState!=TicState.stamping:
                continue

            # Process lines after configured and stamping
            if not re.fullmatch(r"\d+\.\d{12} ch[AB]", line):
                # XXX log stats here
                # print("ignoring TIC line", line)
                continue  # Ignore the line if it doesn't match a timestamp
            dog.pet()
            print("got TIC data", line)
            sample = {"ppsErrorNs": 123}  # placeholder
            # await eventBus.put(Event(nowNs(), "tic", "ppsSample", sample))
            # await asyncio.sleep(1.0)
    finally:
        dog.stop()
        await dogTask
        pass


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
