# ChatGPT wrote this shim to quiet pyright because I was running into a typing mismatch,
# not a runtime bug.
# 	•	serial_asyncio.open_serial_connection() returns a StreamReader and StreamWriter.
# 	•	In typeshed, StreamWriter.transport is typed as asyncio.transports.WriteTransport.
# 	•	But the actual transport for a serial connection implements read methods too
#       (pause_reading/resume_reading) — it’s just not reflected in the type.
#
# So Pyright complains because WriteTransport doesnt declare pause_reading/resume_reading.
# And it also warns that get_extra_info("serial") might be None before you call .fileno().

import asyncio
from types import TracebackType
from typing import Any, Protocol, Self, cast


# Transport that actually supports pause/resume (serial_asyncio provides this at runtime)
class ReadWriteTransport(Protocol):
    def pause_reading(self) -> None: ...
    def resume_reading(self) -> None: ...
    def get_extra_info(self, name: str, default: Any | None = None) -> Any: ...
    serial: Any  # some versions expose the pyserial object here

# Minimal protocol for the underlying pyserial object (we only need fileno())
class HasFileno(Protocol):
    def fileno(self) -> int: ...

def asReadWriteTransport(writer: asyncio.StreamWriter) -> ReadWriteTransport:
    t = writer.transport
    if not hasattr(t, "pause_reading") or not hasattr(t, "resume_reading"):
        raise RuntimeError("transport does not support pause/resume reading")
    return cast(ReadWriteTransport, t)

def getSerialObj(writer: asyncio.StreamWriter) -> HasFileno:
    t = asReadWriteTransport(writer)
    ser = t.get_extra_info("serial", None)
    if ser is None:
        ser = getattr(t, "serial", None)
    if ser is None or not hasattr(ser, "fileno"):
        raise RuntimeError("no underlying serial object with fileno() available")
    return cast(HasFileno, ser)

class PausedReads:
    """Context manager: pause reads on enter, resume on exit."""

    def __init__(self, writer: asyncio.StreamWriter) -> None:
        self.writer = writer
        self.t: ReadWriteTransport | None = None

    def __enter__(self) -> Self:
        self.t = asReadWriteTransport(self.writer)
        self.t.pause_reading()
        return self

    def __exit__(
        self,
        excType: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        # Always resume; return False so any exception propagates
        assert self.t is not None
        self.t.resume_reading()
        return False
