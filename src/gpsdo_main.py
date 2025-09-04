# gpsdo_main.py
import asyncio, json, logging, time, re
import serial_asyncio as serialAsyncio
from dataclasses import dataclass
from enum import Enum
from pyubx2 import UBXMessage
from pynmeagps import NMEAReader

# third party imports (install as needed)
# import aiosqlite

# XXX next up: Move F9T code to seprate class/file
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

async def runF9tStream(port, baud, ubxHandler, nmeaHandler, dropRtcm=True, readSize=4096):
    """
    Continuously read a mixed UBX/NMEA/RTCM stream from `port` and:
      • await ubxHandler(ubxMsg, rawBytes) for each UBX frame
      • await nmeaHandler(nmeaMsg, rawBytes) for each NMEA sentence
    RTCM3 frames are discarded when dropRtcm is True.
    """
    reader, writer = await serialAsyncio.open_serial_connection(url=port, baudrate=baud)
    buf = bytearray()

    try:
        while True:
            chunk = await reader.read(readSize)
            print("got chunk")
            if not chunk:
                await asyncio.sleep(0.01)
                continue
            buf.extend(chunk)

            while True:
                if not buf:
                    break

                # Fast path when buffer starts with a known token
                first = buf[0:1]

                # Handle NMEA lines starting with '$'
                if first == b"$":
                    lineEnd = buf.find(b"\n")
                    if lineEnd == -1:
                        break  # wait for rest of the line
                    rawLine = bytes(buf[: lineEnd + 1])
                    del buf[: lineEnd + 1]
                    # Strip trailing CR/LF for parsing
                    trimmed = rawLine.rstrip(b"\r\n")
                    try:
                        nmeaMsg = NMEAReader.parse(trimmed.decode("ascii", "ignore"))
                        await nmeaHandler(nmeaMsg, rawLine)
                    except Exception as e:
                        # Bad NMEA; resync by continuing
                        print(f"A NMEA parsing error occurred: {e}")
                        pass
                    continue

                # Handle RTCM3 frames starting with 0xD3
                if dropRtcm and first == b"\xD3":
                    if len(buf) < 3:
                        break  # need more for length
                    rtcmLen = ((buf[1] & 0x03) << 8) | buf[2]
                    rtcmFrameLen = 3 + rtcmLen + 3  # header + payload + CRC24Q
                    if len(buf) < rtcmFrameLen:
                        break
                    del buf[:rtcmFrameLen]
                    continue

                # UBX hunt: find sync 0xB5 0x62 anywhere in buffer
                syncIdx = buf.find(b"\xB5\x62")
                if syncIdx == -1:
                    # No UBX in sight; try to align to next known token ($ or 0xD3)
                    nmeaIdx = buf.find(b"$")
                    rtcmIdx = buf.find(b"\xD3") if dropRtcm else -1
                    candidates = [i for i in (nmeaIdx, rtcmIdx) if i != -1]
                    if candidates:
                        cut = min(candidates)
                        if cut > 0:
                            del buf[:cut]
                            continue
                    # Otherwise, keep last byte (might be start of a token) and wait for more data
                    if len(buf) > 1:
                        del buf[:-1]
                    break

                # Discard junk before UBX sync
                if syncIdx > 0:
                    del buf[:syncIdx]

                # Need at least UBX header (sync + class + id + len)
                if len(buf) < 6:
                    break

                payloadLen = buf[4] | (buf[5] << 8)
                frameLen = 6 + payloadLen + 2  # hdr+len+payload+cksum
                if len(buf) < frameLen:
                    break

                rawFrame = bytes(buf[:frameLen])
                try:
                    ubxMsg = UBXMessage.parse(rawFrame)
                except Exception:
                    # Drop one byte to resync and keep scanning
                    del buf[0:1]
                    continue

                # Good UBX frame
                await ubxHandler(ubxMsg, rawFrame)
                del buf[:frameLen]

    except asyncio.CancelledError:
        # Allow cooperative cancellation
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass

async def ubxPrinter(msg, raw):
    # Example: show message identity and iTOW if present
    itow = getattr(msg, "iTOW", None)
    print("UBX", msg.identity, itow)

async def nmeaPrinter(msg, raw):
    # Example: show talker+msg type
    # NMEAMessage.identity typically like "GNGGA" / "GPRMC"
    # print("NMEA", msg)
    pass

async def ticReader(eventBus, port, baud, discard_interval=1.0):
    reader, writer = await serialAsyncio.open_serial_connection(url=port, baudrate=baud)
    start_time = asyncio.get_event_loop().time()  # Get the current time
    discarded_lines = 0

    while True:
        raw = await reader.readline()
        line = raw.decode('utf-8').rstrip()

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
        #asyncio.create_task(f9tReader(eventBus, "/dev/ttyACM1", 9600)),
        asyncio.create_task(runF9tStream(
            port="/dev/ttyACM1",
            baud=9600,
            ubxHandler=ubxPrinter,
            nmeaHandler=nmeaPrinter,
            dropRtcm=True,
        )),
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
    print("main running")
    asyncio.run(main())
