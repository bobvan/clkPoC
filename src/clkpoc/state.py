from enum import Enum
from typing import TypedDict

from .tsTypes import Ts  # XXX this looks questionable


class Mode(Enum):
    Startup = 0
    Step = 1
    CoarseTune = 2
    FineTune = 3


class Health(TypedDict):
    sat: int
    f9tOk: bool
    ticOk: bool


class State:
    def __init__(self) -> None:
        self.mode: Mode = Mode.Startup
        self.dacVal: int = 0
        self.lastDscDev: Ts | None = None
        self.health: Health = {"sat": 0, "f9tOk": False, "ticOk": False}
