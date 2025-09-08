from typing import Any, Iterable, Tuple, Optional, Protocol
import asyncio

class NMEAMessage(Protocol):
    identity: str
    talker: str
    msgID: str
    def serialize(self) -> bytes: ...

class NMEAReader:
    def __init__(self, stream: Any, **kwargs: Any) -> None: ...
    def read(self) -> Tuple[bytes, Optional[NMEAMessage]]: ...
    @staticmethod
    def parse(data: bytes) -> Iterable[NMEAMessage]: ...
