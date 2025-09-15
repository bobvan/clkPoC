
from clkpoc.df.pairPps import PairPps
from clkpoc.dsc import Dsc
from clkpoc.rollingMean import RollingMean
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
        self.lastVal = self.state.dacVal
        self.kp = 0.0000000001
        self.ki = -0.0000001
        #self.ki = 0.0
        self.integ = 0.0
        self.lastAdj = 0.0 # XXX should be lastAdjVal
        self.pairCnt = 0
        self.lastPair: PairTs | None = None
        self.ffeRm15 = RollingMean(15)  # rolling mean of fractional freq error in ppm
        self.pllPi = self.PllPi(hzPerLsb = -4.2034700315e-05,
            codeMin=11400, codeMax=15000, codeInit=self.state.dacVal)


    class PllPi:
        def __init__(self, hzPerLsb: float, codeMin: int, codeMax: int, codeInit: int) -> None:
            # Controller gains in Hz-domain for e in seconds (B=0.05 Hz, zeta=0.7):
            self.kpHz: float = 0.4398230
            self.kiHz: float = 0.0986960
            self.ts: float = 1.0  # seconds per update (PPS rate)

            # Actuator sensitivity (Hz per DAC LSB); your value is ~ -4.20347e-05
            self.hzPerLsb: float = hzPerLsb

            self.codeMin: int = codeMin
            self.codeMax: int = codeMax
            self.code: int = codeInit

            self.prevErr: float | None = None  # seconds
            # XXX don't love this name
            self.freqHz: float = 0.0              # frequency correction (Hz), NOT microhertz

            # Optional: carry fractional LSBs to reduce limit cycles
            self.fracLsb: float = 0.0

        def step(self, errSec: float) -> int:
            # Wrap PPS phase error into (-0.5, 0.5]
            while errSec <= -0.5:
                errSec += 1.0
            while errSec > 0.5:
                errSec -= 1.0

            if self.prevErr is None:
                self.prevErr = errSec

            deltaErr = errSec - self.prevErr

            # Velocity PI in Hz
            self.freqHz = self.freqHz + self.kpHz * deltaErr + self.kiHz * self.ts * errSec
            print(f"  PllPi: err {errSec:.3e} kpHz {self.kpHz} deltaErr {deltaErr:.3e} freqHz {self.freqHz:6e}")

            # Convert frequency correction (Hz) to DAC codes via Hz/LSB
            targetLsb = self.freqHz / self.hzPerLsb + self.fracLsb
            deltaCode = int(round(targetLsb))
            self.fracLsb = targetLsb - float(deltaCode)  # keep residual for next step

            newCode = self.code + deltaCode

            # Clamp and simple anti-windup: keep freqHz consistent with the actually applied code
            if newCode < self.codeMin:
                newCode = self.codeMin
                self.freqHz = (newCode - self.code) * self.hzPerLsb
                self.fracLsb = 0.0
            elif newCode > self.codeMax:
                newCode = self.codeMax
                self.freqHz = (newCode - self.code) * self.hzPerLsb
                self.fracLsb = 0.0
            print(f"fracLsb {self.fracLsb:.3e} targetLsb {targetLsb:.3e} deltaCode {deltaCode} newCode {newCode}")

            self.code = newCode
            self.prevErr = errSec
            return self.code

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
            # Get fractional frequency error in parts per billion
            assert gnsTi != 0.0, "Zero gnsTi in PhaseTrack"
            ffePpb = 1e9*(dscTi-gnsTi)/gnsTi
            ffePpbRm15 = self.ffeRm15.add(ffePpb)
            print(f"PhaseTrack: ffePpmRm15 {ffePpbRm15:8.3f} ", end="")
        else:
            print("PhaseTrack: ffePpm      n/a ", end="")
        self.lastPair = pair

        newVal = self.pllPi.step(dscDev.toPicoseconds() * 1e-12)
        adjVal = self.lastVal - newVal
        accel = adjVal - self.lastAdj
        self.lastAdj = adjVal
        # simple PI loop (replace with your preferred filter)
        #self.integ += dscDev.toPicoseconds()
        #adjVal = self.kp * dscDev.toPicoseconds() + self.ki * self.integ
        #accel = self.lastAdj - adjVal
        #self.lastAdj = adjVal
        #newVal = max(0, min(65535, int(self.state.dacVal - adjVal)))
        #if newVal != self.state.dacVal:
        #    self.state.dacVal = newVal
        #    self.dsc.writeDac(newVal)

        print(f"pairCnt {self.pairCnt:3d}, dscDev {dscDev.elapsedStr()}, "
              f"adj {adjVal:.1f}, accel {accel:.2f}, newVal {newVal}")
