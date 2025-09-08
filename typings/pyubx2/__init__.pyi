from typing import Any, Iterable, Tuple, Optional, Protocol

class UBXMessage(Protocol):
    identity: str
    clsID: Optional[int]
    msgID: Optional[int]
    def serialize(self) -> bytes: ...

class UBXReader:
    def __init__(self, stream: Any, **kwargs: Any) -> None: ...
    def read(self) -> Tuple[bytes, Optional[UBXMessage]]: ...
    @staticmethod
    def parse(data: bytes) -> Iterable[UBXMessage]: ...

# factory function used to build messages
def UBXMessage(
    msgClass: Any, msgID: Any, *args: Any, **kwargs: Any
) -> UBXMessage: ...
