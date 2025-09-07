import asyncio
from typing import Any

async def open_serial_connection(
    *,
    url: str | None = ...,
    baudrate: int | None = ...,
    **kwargs: Any
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]: ...

# (optional) if you also use the transport/loop form:
async def create_serial_connection(
    protocol_factory: Any,
    *args: Any,
    **kwargs: Any
) -> tuple[asyncio.Transport, Any]: ...
