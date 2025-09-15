
from clkpoc.df.pairPps import PairPps
from clkpoc.dsc import Dsc
from clkpoc.state import State
from clkpoc.tsTypes import PairTs


class PhaseTrack:
    """
    Subscribe to PairPps 'pairPps' topic and track
    the phase difference between GNSS and disciplined PPS reference
    timestamps, adjusting the disciplined oscillator to minimize the difference.
    """

    def __init__(self, pairPps: PairPps, state: State) -> None:
        """
        PhaseTrack: Control loop working to keep Dsc phase aligned with Gns.
        """
        # Subscribe to the PairPps publisher for paired PPS events
        pairPps.pub.sub("pairPps", self.onPairPps)
        self.state = state
        self.dsc = Dsc()
        self.state.dacVal = self.dsc.readDac()
        self.kp = 0.0000000001
        self.ki = -0.0000002
        #self.ki = 0.0
        self.integ = 0.0
        self.lastAdj = 0.0
        self.pairCnt = 0
        self.lastPair: PairTs | None = None

    def onPairPps(self, pair: PairTs) -> None:
        # XXX might be better to compute ma5(dscDev) to smooth DAC value changes
        # Deviation of dsc from gns timestamps
        dscDev = pair.gnsTs.refTs.subFrom(pair.dscTs.refTs)
        self.pairCnt += 1
        self.state.lastDscDev = dscDev

        # XXX This should be in its own dataflow someday
        if self.lastPair is not None:
            # Gns time interval since last pair
            gnsTi = self.lastPair.gnsTs.refTs.subFrom(pair.gnsTs.refTs).toUnits()
            dscTi = self.lastPair.dscTs.refTs.subFrom(pair.dscTs.refTs).toUnits()
#            print(f"PhaseTrack: gnsTi {gnsTi} dscTi {dscTi} ")
            ffePpb = 1e9*(dscTi-gnsTi)/gnsTi
            print(f"PhaseTrack: ffePpm {ffePpb:8.3f} ", end="")
        else:
            print("PhaseTrack: ffePpm   n/a ", end="")
        self.lastPair = pair

        # simple PI loop (replace with your preferred filter)
        self.integ += dscDev.toPicoseconds()
        adjVal = self.kp * dscDev.toPicoseconds() + self.ki * self.integ
        accel = self.lastAdj - adjVal
        self.lastAdj = adjVal
        newVal = max(0, min(65535, int(self.state.dacVal - adjVal)))
        if newVal != self.state.dacVal:
            self.state.dacVal = newVal
            self.dsc.writeDac(newVal)
        print(f"pairCnt {self.pairCnt:3d}, dscDev {dscDev.elapsedStr()}, adj {adjVal:.1f}, accel {accel:.1f}, newVal {newVal}")
