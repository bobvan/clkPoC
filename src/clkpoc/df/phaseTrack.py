
from clkpoc.df.pairPps import PairPps
from clkpoc.dsc import Dsc
from clkpoc.tsTypes import PairTs


class PhaseTrack:
    """
    Subscribe to PairPps 'pairPps' topic and track
    the phase difference between GNSS and disciplined PPS reference
    timestamps, adjusting the disciplined oscillator to minimize the difference.
    """

    def __init__(self, pairPps: PairPps) -> None:
        """
        pairPps: the PairPps instance publisher
        """
        # Subscribe to the PairPps publisher for paired PPS events
        pairPps.pub.sub("pairPps", self.onPairPps)
        self.dsc = Dsc()
        self.dsc.writeDac(15000)

    def onPairPps(self, pair: PairTs) -> None:
        # Compute delta between reference timestamps
        # XXX might be better to compute ma5(delta) to avoid false positives
        # Deviation of dsc from gns timestamps
        dscDev = pair.gnsTs.refTs.subFrom(pair.dscTs.refTs)
