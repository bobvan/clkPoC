import asyncio
import contextlib
import re
import termios
from enum import Enum
from typing import Any

import serial_asyncio as serialAsyncio

from clkpoc.clkTypes import TicTs, Ts
from clkpoc.publisher import Publisher
from clkpoc.quietWatch import QuietWatch
from clkpoc.serialAsyncioShim import PausedReads, getSerialObj


class TicState(Enum):
    # This should be a state variable for debug inspection
    startup = 0  # We are ready to send a character to get the config menu
    config1 = 1  # Have sent character, waiting for the "choose one:" prompt
    config2 = 2  # Have sent reset, waiting for 2nd "choose one:" prompt
    stamping = 3  # Have written config changes and are now timestamping


class TIC:
    def __init__(self, eventBus: asyncio.Queue[Any], port: str, baud: int):
        self.eventBus = eventBus
        self.port = port
        self.baud = baud
        self.ticState = TicState.startup
        self.dog = QuietWatch(name=port, warnAfterSec=10)
        self.pps = Publisher("TIC", warnIfSlowMs=5.0)

    async def run(self):
        reader, writer = await serialAsyncio.open_serial_connection(
            url=self.port, baudrate=self.baud
        ) # When this is changed, note copy below for reopening

        # If the last guy to open the TIC's serial port didn't set HUPCL, we may see
        # garbled output at first, then timestamps continuing from the previous run.
        # To avoid that when we're done, we want to leave it in a reset state for our
        # next open, so we set HUPCL if it's not set.
        #
        # Pause callbacks while we tweak termios
        with PausedReads(writer):
            serialObj = getSerialObj(writer)
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
                    # Python 3.8+; waits for transport shutdown
                    await writer.wait_closed()
                await asyncio.sleep(0.1)
                # Re-open serial connection, now with HUPCL for next time we open it
                reader, writer = await serialAsyncio.open_serial_connection(
                    url=self.port, baudrate=self.baud
                )

        # Opening the port this way means the TIC is always in its startup state.
        # We run through the config menu to quickly reset it to all defaults and start
        # timestamping quickly.
        ticState = TicState.startup

        dog = QuietWatch(name=self.port, warnAfterSec=10)
        dogTask = asyncio.create_task(self.dog.run())

        try:
            while True:
                raw = await reader.readline()
                # XXX this is the spot to catch SerialException when TIC is unplugged
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

                # Process lines after TIC is configured and in stamping state.
                # The ASCII string representation of timestamps read straight from
                # the TIC use standard floating point representations, and it
                # would be convenient to parse them that way, but Python's float
                # only has 15 digits of precision, and the TIC outputs 12 digits
                # after the decimal point, so precision could be lost after 100
                # seconds. So we parse the integer and fractional parts separately.
                pat =  re.compile(
                    r"(?P<integerStr>\d+)\.(?P<fracStr>\d{12}) ch(?P<chan>[AB])")
                match = pat.fullmatch(line)
                if not match:
                    # XXX log stats here
                    # print("ignoring TIC line", line)
                    continue  # Ignore the line if it doesn't match a timestamp
                dog.pet()
                capTs = Ts.now()
                integerStr, fracStr, chan = match.group('integerStr', 'fracStr', 'chan')
                ppsTs = Ts.fromStr(integerStr, fracStr)
                ticTs = TicTs(ts=ppsTs, capTs=capTs, chan=chan)
                print("got TIC data", ticTs)
                # sample = {"ppsErrorNs": 123}  # placeholder
                # await eventBus.put(Event(nowNs(), "tic", "ppsSample", sample))
                # await asyncio.sleep(1.0)
        finally:
            self.dog.stop()
            await dogTask
