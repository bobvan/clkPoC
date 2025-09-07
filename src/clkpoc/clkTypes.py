# pyright: basic
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self


@dataclass
class Ts:
    secs: int # Arbitray precision ints can be in any future relative to the epoch
    frac: float # With the 15-digit precision of floats, we can resolve femtoseconds

    # Assertion: denormalized timestamps should be explicitly handled at their
    # creation time, rather than transparently handled later when accessed.
    # Nonetheless, assertions watch for denormalized timestamps before access.
    # Keeping the fractional part in the range [0, 1) maintains precision.

    def normalizeByIncDec(self):
        # Normalize by incrementing or decrementing the integer part
        if self.frac < 0:
            self.secs -= 1
            self.frac += 1
        if self.frac >= 1:
            self.secs += 1
            self.frac -= 1
        assert (self.frac >= 0
            and self.frac < 1
            ), f"Fractional result of normailzation {self.frac} must be in [0, 1)"
        return

    def subFrom(self, minuend):
        assert (minuend.frac >= 0
            and minuend.frac < 1
            ), f"Fractional part of minuend {minuend.frac} must be in [0, 1)"
        self.secs = minuend.secs - self.secs
        self.frac = minuend.frac - self.frac
        self.normalizeByIncDec()
        return

    @staticmethod
    def now() -> Self:
        # Construct Ts set to current time from system clock
        ns = time.time_ns()
        return Ts(secs=ns // 1_000_000_000, frac=(ns % 1_000_000_000) / 1_000_000_000)

    @staticmethod
    def fromStr(integerStr: str, fracStr: str) -> Self:
        # Construct Ts from separate integer and fractional strings
        intPart = int(integerStr)
        fracPart = float("0." + fracStr)
        return Ts(secs=intPart, frac=fracPart)

    # Return fractional part as string
    def fracStr(self, places: int = 12) -> str:
        assert (self.frac >= 0
            and self.frac < 1
            ), f"Fractional result of normailzation {self.frac} must be in [0, 1)"
        return f"{self.frac:.{places}f}"[2:]

    # N.B. The UTC formatting code below assumes that frac has no precision
    # beyond nanoseconds. A reasonable assumption for timestamps that come
    # from time_ns().

    def isoUtc(self) -> str:
        base = datetime.fromtimestamp(self.secs, tz=UTC).strftime(
            "%Y-%m-%dT%H:%M:%S")
        return f"{base}.{self.fracStr(places=9)}Z"

    def isoLocal(self) -> str:
        # system local zone with offset; include 9-digit fraction
        dt = datetime.fromtimestamp(self.secs).astimezone()  # local tz
        base = dt.strftime("%Y-%m-%dT%H:%M:%S")
        off = dt.strftime("%z")  # e.g. -0500
        off = off[:-2] + ":" + off[-2:] if off else ""
        return f"{base}.{self.fracStr(places=9)}{off}"

    def elapsedStr(self) -> str:
        return f"{self.secs}.{self.fracStr()}s"

    def __repr__(self) -> str:
        # unambiguous developer form (great for logs with %r)
        sec, nsec = self.asSecAndNsec()
        return f"Ts(secs={sec}, nsec={nsec})"

    def __str__(self):
        if self.secs > 60*60*24*365:
            return self.isoLocal()
        else:
            return self.elapsedStr()

    def __format__(self, spec: str) -> str:
        # custom mini-format:
        #   U = ISO-8601 UTC, L = ISO-8601 local, E = elapsed seconds
        spec = (spec or "L").upper()
        if spec == "U":
            return self.isoUtc()
        if spec == "L":
            return self.isoLocal()
        if spec == "E":
            return self.elapsedStr()
        return str(self)  # fallback

@dataclass
class TicTs:
    ts: Ts
    capTs: Ts
    chan: str

    def __str__(self):
        return f"cap {self.capTs:L} tic {self.ts:E} chan {self.chan}"


@dataclass
class DscTs:
    ts: Ts
    capTs: Ts


@dataclass
class GnsTs:
    ts: Ts
    capTs: Ts
