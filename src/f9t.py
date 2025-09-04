import asyncio
import logging
from quietDog import QuietDog

import serial_asyncio as serialAsyncio
from pynmeagps import NMEAReader
from pyubx2 import UBXMessage


class F9T:
    def __init__(self, eventBus, port, baud):
        self.eventBus = eventBus
        self.port = port
        self.baud = baud

    async def ubxPrinter(self, msg, raw):
        # Example: show message identity and iTOW if present
        itow = getattr(msg, "iTOW", None)
        print("UBX", msg.identity, itow)

    async def nmeaPrinter(self, msg, raw):
        # Example: show talker+msg type
        # NMEAMessage.identity typically like "GNGGA" / "GPRMC"
        #print("NMEA", msg)
        pass

    async def runF9tStream(
        self,
        ubxHandler=ubxPrinter,
        nmeaHandler=nmeaPrinter,
        dropRtcm=True,
        readSize=4096,
    ):
        """
        Continuously read a mixed UBX/NMEA/RTCM stream from `port` and:
        • await ubxHandler(ubxMsg, rawBytes) for each UBX frame
        • await nmeaHandler(nmeaMsg, rawBytes) for each NMEA sentence
        RTCM3 frames are discarded when dropRtcm is True.
        """
        reader, writer = await serialAsyncio.open_serial_connection(
            url=self.port, baudrate=self.baud
        )
        dog = QuietDog(name=self.port)
        dogTask = asyncio.create_task(dog.run())
        buf = bytearray()

        try:
            while True:
                chunk = await reader.read(readSize)
                if not chunk:
                    logging.warning(f"{self.port}: F9T serial closed or returned zero bytes")
                    break
                dog.pet()
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
                            nmeaMsg = NMEAReader.parse(
                                trimmed.decode("ascii", "ignore")
                            )
                            await nmeaHandler(self, nmeaMsg, rawLine)
                        except Exception as e:
                            # Bad NMEA; resync by continuing
                            print(f"A NMEA parsing error occurred: {e}")
                            pass
                        continue

                    # Handle RTCM3 frames starting with 0xD3
                    if dropRtcm and first == b"\xd3":
                        if len(buf) < 3:
                            break  # need more for length
                        rtcmLen = ((buf[1] & 0x03) << 8) | buf[2]
                        rtcmFrameLen = 3 + rtcmLen + 3  # header + payload + CRC24Q
                        if len(buf) < rtcmFrameLen:
                            break
                        del buf[:rtcmFrameLen]
                        continue

                    # UBX hunt: find sync 0xB5 0x62 anywhere in buffer
                    syncIdx = buf.find(b"\xb5\x62")
                    if syncIdx == -1:
                        # No UBX in sight; try to align to next known token ($ or 0xD3)
                        nmeaIdx = buf.find(b"$")
                        rtcmIdx = buf.find(b"\xd3") if dropRtcm else -1
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

        # XXX this would be the spot to catch SerialException when F9T is unplugged
        except asyncio.CancelledError:
            # Allow cooperative cancellation
            pass
        finally:
            dog.stop()
            await dogTask
            try:
                writer.close()
            except Exception:
                pass
