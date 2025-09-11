import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar, Self
from zoneinfo import ZoneInfo  # Python 3.9+
from tzlocal import get_localzone_name


# A fixed point representaiton for timestamps.
@dataclass(frozen=True)
class Tsn:
    # Note toPicoseconds() below must change if fracDigs != 12
    fracDigs: ClassVar[int] = 12 # Number of digits to right of decimal point
    unitsPerSecond: ClassVar[int] = 10 ** fracDigs

    # Units since Unix epoch (POSIX time; no leap seconds, can be negative)
    units: int

    @classmethod
    def fromParts(cls: type[Self], sec: int, frac: int) -> Self:
        return cls(sec * cls.unitsPerSecond + frac)

    @classmethod
    def fromPicoseconds(cls: type[Self], totalPs: int) -> Self:
        return cls(totalPs)

    @classmethod
    def fromFloat(cls: type[Self], x: float) -> Self:
        # exact float -> rational -> round once to picoseconds (round-to-even)
        n, d = x.as_integer_ratio()
        t, rem = divmod(n * cls.unitsPerSecond, d)
        if rem * 2 > d or (rem * 2 == d and (t & 1) == 1):
            t += 1
        return cls(int(t))

    @classmethod
    def fromStrs(cls: type[Self], integerStr: str, fracStr: str) -> Self:
        # Construct Ts from separate integer and fractional strings
        intPart = int(integerStr)
        sigDigs = fracStr[:cls.fracDigs]
        fracPart = int(sigDigs) * 10**(cls.fracDigs-len(sigDigs))
        return intPart*cls.unitsPerSecond + fracPart

    @classmethod
    def now(cls: type[Self]) -> Self:
        # Construct Ts set to current time from system clock
        ns = time.time_ns()
        return cls(units = ns * 10 ** (cls.fracDigs - 9))

    def toPicoseconds(self) -> int:
        return self.units

    def toFloorParts(self) -> tuple[int, int]:
        # Get floor seconds and nonnegative fraction using floor division
        s, f = divmod(self.units, type(self).unitsPerSecond)
        return int(s), int(f)  # 0 <= f < unitsPerSecond

    def add(self: Self, other: Self) -> Self:
        return type(self)(self.units + other.units)

    def sub(self: Self, other: Self) -> Self: # XXX make this subFrom()
        return type(self)(self.units - other.units)

    def toDecimal(self, places: int = fracDigs) -> str:
        if places < 0 or places > self.fracDigs:
            raise ValueError("places must be between 0 and {fracDigs}")
        d = type(self).unitsPerSecond
        sign = "-" if self.units < 0 else ""
        absUnits = -self.units if self.units < 0 else self.units
        whole, fracPs = divmod(absUnits, d)

        if places == self.fracDigs:
            digits = fracPs
        else:
            scale = 10 ** (self.fracDigs - places)
            q, rem = divmod(fracPs, scale)
            # round-to-even
            if rem * 2 > scale or (rem * 2 == scale and (q & 1) == 1):
                q += 1
            if q == 10 ** places:  # carry into whole
                q = 0
                whole += 1
            digits = q

        if places == 0:
            return f"{sign}{whole}"
        return f"{sign}{whole}.{digits:0{places}d}"

    def __str__(self) -> str:
        return self.toDecimal(self.fracDigs)

    # ---- ISO 8601 formatting ----

    def toIso8601(self, places: int = fracDigs, zone: str | None = "Z") -> str:
        """
        Render as ISO 8601 extended format.
        places: 0..fracDigs fractional digits
        zone: "Z" for UTC (default), or an IANA zone like "America/Chicago".
        """
        if places < 0 or places > self.fracDigs:
            raise ValueError("places must be between 0 and {fracDigs}")

        # Split into seconds and picoseconds
        sec, ps = self.toFloorParts()

        # Round the fractional ps to requested places (round-to-even)
        if places == self.fracDigs:
            fracDigits = ps
        else:
            scale = 10 ** (self.fracDigs - places)
            q, rem = divmod(ps, scale)
            if rem * 2 > scale or (rem * 2 == scale and (q & 1) == 1):
                q += 1
            # carry across the second if we rounded to 1.000… at this precision
            if q == 10 ** places:
                q = 0
                sec += 1
            fracDigits = q

        # Choose timezone
        if zone == "Z" or zone is None:
            tzinfo = UTC
            tzSuffix = "Z"
        else:
            tzinfo = ZoneInfo(zone)
            tzSuffix = ""  # will compute later
            # Build a datetime to compute the numeric offset string
            # (we’ll rebuild it again after sec possibly changed by rounding)
            pass

        # Build wall-clock fields from whole seconds *after* rounding/carry
        dt = datetime.fromtimestamp(sec, tz=tzinfo)

        # If non-UTC zone was requested, compute "+HH:MM" or "-HH:MM"
        if tzinfo is UTC:
            suffix = tzSuffix
        else:
            off = dt.utcoffset()
            if off is None:
                # Shouldn't happen for a real zone; fall back to 'Z'
                suffix = "Z"
            else:
                tot = int(off.total_seconds())
                sign = "+" if tot >= 0 else "-"
                tot = abs(tot)
                hh, rem = divmod(tot, 3600)
                mm, _ = divmod(rem, 60)
                suffix = f"{sign}{hh:02d}:{mm:02d}"

        # Base timestamp without fraction
        base = dt.strftime("%Y-%m-%dT%H:%M:%S")

        # Append fraction if requested
        if places == 0:
            return f"{base}{suffix}"
        return f"{base}.{fracDigits:0{places}d}{suffix}"

    def elapsedStr(self) -> str:
        return self.toDecimal() + 's'

    def isoUtc(self, places: int = fracDigs) -> str:
        return self.toIso8601(places=places, zone="Z")

    def isoLocal(self, places: int = fracDigs) -> str:
        return self.toIso8601(places, get_localzone_name())

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

    def __repr__(self) -> str:
        # unambiguous developer form (great for logs with %r)
        return f"Ts(units={self.units})"
