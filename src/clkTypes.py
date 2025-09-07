from dataclasses import dataclass


@dataclass
class Ts:
    secs: int
    frac: int

    def __str__(self):
        frac = f"{self.frac}"
        # Remove leading "0." if present
        if frac.startswith("0."):
            frac = frac[1:]
        return f"{self.secs}{frac}"

    def subFrom(self, minuend):
        assert (minuend.frac >= 0
            and minuend.frac < 1
            ), f"Fractional part of minuend {minuend.frac} must be in [0, 1)"
        secDiff = minuend.secs - self.secs
        fracDiff = minuend.frac - self.frac
        if fracDiff < 0:
            secDiff -= 1
            fracDiff += 1
        if fracDiff >= 1:
            secDiff += 1
            fracDiff -= 1
        assert (fracDiff >= 0
            and fracDiff < 1
            ), f"Fractional part of result {fracDiff} must be in [0, 1)"
        return Ts(secDiff, fracDiff)


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
