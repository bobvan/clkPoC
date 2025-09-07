# pyright: basic
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self


@dataclass
class Ts:
    secs: int # Arbitray precision ints can be in any future relative to the epoch
    frac: float # With the 15-digit precision of floats, we can resolve femtoseconds

    # Denormalized timestamps should be explicitly handled, rather than
    # transparently handled.
    # Keeping the fractional part in the range [0, 1) maintains precision.

    def normalizeByIncDec(self, ts: Self) -> Self:
        # Normalize by incrementing or decrementing the integer part
        sec = ts.secs
        frac = ts.frac
        if frac < 0:
            sec -= 1
            frac += 1
        if frac >= 1:
            sec += 1
            frac -= 1
        assert (frac >= 0
            and frac < 1
            ), f"Fractional result of normailzation {frac} must be in [0, 1)"
        return Ts(sec, frac)

    def subFrom(self, minuend):
        assert (minuend.frac >= 0
            and minuend.frac < 1
            ), f"Fractional part of minuend {minuend.frac} must be in [0, 1)"
        secDiff = minuend.secs - self.secs
        fracDiff = minuend.frac - self.frac
        res = self.normalizeByIncDec(Ts(secDiff, fracDiff))
        return res

    def asSecAndNsec(self) -> tuple[int, int]:
        nsec = int(round(self.frac * 1_000_000_000))
        sec = self.secs
        if nsec >= 1_000_000_000:
            sec += 1
            nsec -= 1_000_000_000
        if nsec < 0:
            sec -= 1
            nsec += 1_000_000_000
        return sec, nsec

    def isoUtc(self) -> str:
        sec, nsec = self.asSecAndNsec()
        base = datetime.fromtimestamp(sec, tz=UTC).strftime(
            "%Y-%m-%dT%H:%M:%S")
        return f"{base}.{nsec:09d}Z"

    def isoLocal(self) -> str:
        # system local zone with offset; include 9-digit fraction
        sec, nsec = self.asSecAndNsec()
        dt = datetime.fromtimestamp(sec).astimezone()  # local tz
        base = dt.strftime("%Y-%m-%dT%H:%M:%S")
        off = dt.strftime("%z")  # e.g. -0500
        off = off[:-2] + ":" + off[-2:] if off else ""
        return f"{base}.{nsec:09d}{off}"

    def elapsedStr(self) -> str:
        sec, nsec = self.asSecAndNsec()
        return f"{sec}.{nsec:09d}s"

    def __repr__(self) -> str:
        # unambiguous developer form (great for logs with %r)
        sec, nsec = self.asSecAndNsec()
        return f"Ts(secs={sec}, nsec={nsec})"

    def __str__(self):
        frac = f"{self.frac}"
        # Remove leading "0." if present
        if frac.startswith("0."):
            frac = frac[1:]
        return f"{self.secs}{frac}"

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


@dataclass
class DscTs:
    ts: Ts
    capTs: Ts


@dataclass
class GnsTs:
    ts: Ts
    capTs: Ts
