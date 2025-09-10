import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar, Self


@dataclass
class Ts:
    fracUnitsPerSecond: ClassVar[int] = 1_000_000_000_000  # 1e12 ps, see next line
    fracResLog10: ClassVar[int] = 12  # log10 of fracUnitsPerSecond

    secs: int # Arbitray precision ints can be in any future or past relative to the epoch
    frac: int # 0 <= frac < fracUnitsPerSecond

    # N.B. We think of timestamps as strictly positive, but the result of subtraction
    # can be negative.
    # Negative secs, negative frac, or both negative, indicate a negative timestamp.
    # A normalized timestamp has frac in the range (-1, 1).

#    def isNeg(self) -> bool:
#        return (self.secs < 0 or self.frac < 0)

    # Assertion: denormalized timestamps should be explicitly handled at their
    # creation time, rather than transparently handled later when accessed.
    # Nonetheless, assertions watch for denormalized timestamps before access.

    def isNormalized(self) -> bool:
        return (self.frac >= 0 and self.frac < self.fracUnitsPerSecond)

    # Normalize the timestamp by incrementing or decrementing the integer part.
    # This covers the range of denormalization that can occur when subtracting.
    # Implement normalization by other means to cover larnger ranges later if needed.
    def normalizeByIncDec(self) -> None:
        if self.frac < 0:
            self.secs -= 1
            self.frac += self.fracUnitsPerSecond
        elif self.frac >= self.fracUnitsPerSecond:
            self.secs += 1
            self.frac -= self.fracUnitsPerSecond
        assert (self.isNormalized()
            ), f"Result of normalizationByDec not normalized {self!r}"
        return

    def subFrom(self, minuend: Self) -> None:
        assert (minuend.isNormalized()
            ), f"Minuend not normalized {minuend}"
        self.secs = minuend.secs - self.secs
        self.frac = minuend.frac - self.frac
        self.normalizeByIncDec()
        return

    @classmethod
    def now(cls: type[Self]) -> Self:
        # Construct Ts set to current time from system clock
        ns = time.time_ns()
        return cls(secs=ns // 1_000_000_000, frac=1_000*(ns % 1_000_000_000))

    @classmethod
    def fromStr(cls: type[Self], integerStr: str, fracStr: str) -> Self:
        # Construct Ts from separate integer and fractional picosecond strings
        intPart = int(integerStr)
        fracPart = int(fracStr)
        return cls(secs=intPart, frac=fracPart)

    @classmethod
    def fromFloat(cls: type[Self], x: float) -> Self:
        # Construct Ts from floating point seconds
        n, d = x.as_integer_ratio()  # exact
        s = n // d                   # floor seconds (OK for negatives)
        r = n - s * d                # remainder in [0, d)
        t = r * cls.fracUnitsPerSecond
        q, rem = divmod(t, d)        # q = unrounded ps, rem = remainder
        # round-to-even at half
        if rem * 2 > d or (rem * 2 == d and (q & 1) == 1):
            q += 1
        if q >= cls.fracUnitsPerSecond:  # carry if we rounded to 1e12 ps
            s += 1
            q -= cls.fracUnitsPerSecond
        return cls(int(s), int(q))

    # Return fractional part as string, without leading "0." or sign.
    # N.B. Digits are truncated, not rounded when places < fracResLog10.
    # XXX Delete or fix name confusion below
    def fracStr(self, places: int = fracResLog10) -> str:
        assert (self.isNormalized()
            ), f"Fractional string on denormalized timestamp {self!r}"
        return f"{self.frac:012d}"[:places]

    def wholeAndDigits(self: Self, places: int = fracResLog10) -> tuple[int, int]:
        if places < 0 or places > self.fracResLog10:
            raise ValueError("places must be between 0 and {fracResLog10}")
        d = type(self).fracUnitsPerSecond
        negative = self.secs < 0 and self.frac != 0

        if not negative:
            whole = self.secs
            fracPs = self.frac
        else:
            whole = self.secs + 1               # borrow for display
            fracPs = d - self.frac

        if places == self.fracResLog10:
            digits = fracPs
        else:
            scale = 10 ** (self.fracResLog10 - places)
            q, rem = divmod(fracPs, scale)
            # round-to-even at half
            if rem * 2 > scale or (rem * 2 == scale and (q & 1) == 1):
                q += 1
            limit = 10 ** places
            if q == limit:                      # rounded up to 1.000… carry into whole
                q = 0
                whole = whole - 1 if negative else whole + 1
            digits = q

        return int(whole), int(digits)

    def fracString(self: Self, places: int = fracResLog10) -> str:
        _, digits = self.wholeAndDigits(places)
        # whole is computed in case rounding carried; digits are the rendered fraction
        return f"{digits:0{places}d}"

    def toDecimal(self: Self, places: int = fracResLog10) -> str:
        whole, digits = self.wholeAndDigits(places)
        sign = "-" if self.secs < 0 else ""
        absWhole = -whole if whole < 0 else whole
        if places == 0:
            return f"{sign}{absWhole}"
        return f"{sign}{absWhole}.{digits:0{places}d}"

    # N.B. The UTC formatting code below assumes that frac has no precision
    # beyond nanoseconds. A reasonable assumption for timestamps that come
    # from time_ns().

    def isoUtc(self) -> str:
        if not self.isNormalized():
            return self.__repr__()
        frac = self.fracStr(places=9)
        base = datetime.fromtimestamp(self.secs, tz=UTC).strftime(
            "%Y-%m-%dT%H:%M:%S")
        return f"{base}.{frac}Z"

    def isoLocal(self) -> str:
        # system local zone with offset; include 9-digit fraction
        if not self.isNormalized():
            return self.__repr__()
        frac = self.fracStr(places=9)
        dt = datetime.fromtimestamp(self.secs).astimezone()  # local tz
        base = dt.strftime("%Y-%m-%dT%H:%M:%S")
        off = dt.strftime("%z")  # e.g. -0500
        off = off[:-2] + ":" + off[-2:] if off else ""
        return f"{base}.{frac}{off}"

    def elapsedStr(self) -> str:
        if not self.isNormalized():
            return self.__repr__()
        return self.toDecimal(self.fracResLog10) + 's'

# Break glass in case of float
#    def __init__(self, secs: int, frac: int):
#        if not isinstance(secs, int):
#            raise TypeError(f"'secs' must be an integer, not {type(secs).__name__}")
#        if not isinstance(frac, int):
#            raise TypeError(f"'frac' must be an integer, not {type(frac).__name__}")
#        self.secs = secs
#        self.frac = frac

    def __repr__(self) -> str:
        # unambiguous developer form (great for logs with %r)
        return f"Ts(secs={self.secs}, frac={self.frac})"

    def __str__(self):
        if self.secs > 60*60*24*365:
            return self.isoLocal()
        else:
            return self.elapsedStr()

    def __format__(self, spec: str) -> str:
        # custom mini-format:
        #   U = ISO-8601 UTC, L = ISO-8601 local, E = elapsed seconds
        #   A = Automatic (default): Elapsed if < 1 year since epoch, else local
        spec = (spec or "A").upper()
        if spec == "U":
            return self.isoUtc()
        if spec == "L":
            return self.isoLocal()
        if spec == "E":
            return self.elapsedStr()
        if spec == "A":
            return str(self)
        # XXX add match an warn here if not matched
        return str(self)  # fallback

@dataclass
class TicTs:
    refTs: Ts # Event timestamp on TIC's reference clock
    capTs: Ts # Event timestamp capture time on host clock

    def __str__(self):
        return f"cap {self.capTs:L} tic {self.refTs:E}"


# Paired up timestamps from GNSS PPS and disciplined oscillator PPS
@dataclass
class PairTs:
    gnsTs: TicTs
    dscTs: TicTs

    def __str__(self):
        return f"gns {self.gnsTs} dsc {self.dscTs}"

#@dataclass
#class DscTs:
#    ts: Ts
#    capTs: Ts


#@dataclass
#class GnsTs:
#    ts: Ts
#    capTs: Ts
