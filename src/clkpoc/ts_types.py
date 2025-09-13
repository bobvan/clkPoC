from dataclasses import dataclass

from clkpoc.tsn import Tsn


@dataclass(frozen=True)
class TicTs:
    refTs: Tsn  # Event timestamp on TIC's reference clock
    capTs: Tsn  # Event timestamp capture time on host clock

    def __str__(self) -> str:
        return f"cap {self.capTs:L} tic {self.refTs:E}"


# Paired up timestamps from GNSS PPS and disciplined oscillator PPS
@dataclass(frozen=True)
class PairTs:
    gnsTs: TicTs
    dscTs: TicTs

    def __str__(self) -> str:
        return f"gns {self.gnsTs} dsc {self.dscTs}"
