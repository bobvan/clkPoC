# pyright: basic
import asyncio
from typing import Any, cast

from typing_extensions import Protocol


# A tiny protocol that matches what serial_asyncio’s transport actually offers
class ReadWriteTransport(Protocol):
    def pause_reading(self) -> None: ...
    def resume_reading(self) -> None: ...
    def get_extra_info(self, name: str, default: Any | None = None) -> Any: ...
    # .serial attribute exists on pyserial-asyncio transports; treat as optional
    serial: Any  # you can narrow this to serial.SerialBase if you import pyserial types

def asReadWriteTransport(writer: asyncio.StreamWriter) -> ReadWriteTransport:
    t = writer.transport
    # Optional safety: assert the transport really supports pause/resume at runtime
    if not hasattr(t, "pause_reading") or not hasattr(t, "resume_reading"):
        raise RuntimeError("transport does not support pause/resume reading")
    return cast(ReadWriteTransport, t)

def getSerialObj(writer: asyncio.StreamWriter) -> Any:
    t = asReadWriteTransport(writer)
    ser = t.get_extra_info("serial", None)
    if ser is None:
        # some versions also expose .serial attribute
        ser = getattr(t, "serial", None)
    if ser is None:
        raise RuntimeError("no underlying serial object available")
    return ser

class pausedReads:
    """Context manager to pause/resume reads around critical sections."""
    def __init__(self, writer: asyncio.StreamWriter):
        self.writer = writer
        self.t: ReadWriteTransport | None = None

    def __enter__(self):
        self.t = asReadWriteTransport(self.writer)
        self.t.pause_reading()
        return self

    def __exit__(self, exc_type, exc, tb):
        assert self.t is not None
        self.t.resume_reading()
        return False
