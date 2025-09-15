from enum import Enum
from typing import TypedDict

from .tsTypes import Ts


class Mode(Enum):
    idle = 0
    disciplining = 1
    holdover = 2
    fault = 3


class Health(TypedDict):
    sat: int
    f9tOk: bool
    ticOk: bool


class State:
    def __init__(self) -> None:
        self.mode: Mode = Mode.idle
        self.dacVal: int = 0
        self.lastDscDev: Ts | None = None
        self.health: Health = {"sat": 0, "f9tOk": False, "ticOk": False}
