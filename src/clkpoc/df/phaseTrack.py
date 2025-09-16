
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
        self.ffeRm15 = RollingMean(15)  # rolling mean of fractional freq error in ppb
        # XXX consider opening up codeMin/Max
        self.pllWithFll = self.PllWithFll(hzPerLsb = -4.2034700315e-05,
            codeMin=11400, codeMax=15000, codeInit=self.state.dacVal)



    class PllWithFll:
        """
        Hybrid PLL+FLL controller for PPS disciplining.

        Inputs to step():
        errSec  -> phase error in seconds (osc - ref), already wrapped to (-0.5, 0.5]

        Output:
        next DAC code (int)

        Internals:
        - Controller output kept in Hz, converted to DAC via hzPerLsb (can be negative).
        - FLL active when |err| >= engageLowSec, fully on at |err| >= engageHighSec.
        """

        def __init__(
            self,
            hzPerLsb: float,             # Hz per DAC LSB (your slope, can be negative)
            codeMin: int,
            codeMax: int,
            codeInit: int,
            f0Hz: float = 10e6,          # nominal frequency, e.g., 10e6
            sampleTime: float = 1.0,     # loop period in seconds (PPS)
            # bandwidths and damping
            trackBandHz: float = 0.05,   # quiet tracking bandwidth
            acquireBandHz: float = 0.25, # faster acquisition bandwidth
            zeta: float = 0.7,
            # FLL assist settings
            engageHighNs: float = 400.0, # ≥ this, FLL fully engaged
            engageLowNs: float = 20.0,   # ≤ this, FLL off
            fllGain: float = 0.9,        # scale on frequency estimate, 0.5..1.0 typical
            fllMaxHz: float = 0.001,     # cap FLL shove per update (Hz)
            # derivative smoothing for FLL (EMA on phase)
            emaAlpha: float = 0.2        # 0=no smooth, 1=heavy smooth; choose small (0.1..0.3)
        ) -> None:
            # plant / actuator
            self.f0Hz: float = f0Hz
            self.hzPerLsb: float = hzPerLsb

            # DAC limits/state
            self.codeMin: int = codeMin
            self.codeMax: int = codeMax
            self.code: int = codeInit

            # timing
            self.ts: float = sampleTime

            # design params
            self.zeta: float = zeta
            self.trackBandHz: float = trackBandHz
            self.acquireBandHz: float = acquireBandHz

            # convert ns thresholds to s
            self.engageHighSec: float = engageHighNs * 1e-9
            self.engageLowSec: float = engageLowNs * 1e-9

            # FLL params
            self.fllGain: float = fllGain
            self.fllMaxHz: float = fllMaxHz

            # controller states
            self.freqHz: float = 0.0              # controller output in Hz
            self.prevErr: float | None = None  # previous raw phase error (s)
            self.emaErr: float | None = None   # smoothed phase error for derivative
            self.emaAlpha: float = emaAlpha
            self.fracLsb: float = 0.0             # sigma-delta accumulator (LSB fraction)

            # start in acquisition bandwidth, switch automatically as error shrinks
            self.kpHz: float = 0.0
            self.kiHz: float = 0.0
            self.setPllBandwidth(self.acquireBandHz)

        def setPllBandwidth(self, bandHz: float) -> None:
            """Set PLL PI gains for a target closed-loop bandwidth bandHz (Hz)."""
            omega = 2.0 * 3.141592653589793 * bandHz
            # continuous-time velocity-PI gains (phase error in seconds, output in Hz)
            self.kpHz = 2.0 * self.zeta * omega
            self.kiHz = omega * omega

        def blendAlpha(self, absErr: float) -> float:
            """FLL blend: 1 at ≥ engageHighSec, 0 at ≤ engageLowSec, linear in-between."""
            if absErr >= self.engageHighSec:
                return 1.0
            if absErr <= self.engageLowSec:
                return 0.0
            return (absErr - self.engageLowSec) / (self.engageHighSec - self.engageLowSec)

        def clamp(self, x: float, lo: float, hi: float) -> float:
            return lo if x < lo else hi if x > hi else x

        def step(self, errSec: float) -> int:
            # phase wrap (safety; caller should usually pre-wrap)
            while errSec <= -0.5:
                errSec += 1.0
            while errSec > 0.5:
                errSec -= 1.0

            absErr = abs(errSec)

            # bandwidth scheduling: fast when far, quiet when near
            if absErr > self.engageLowSec * 1.2:
                # use acquisition bandwidth
                self.setPllBandwidth(self.acquireBandHz)
            else:
                # use tracking bandwidth
                self.setPllBandwidth(self.trackBandHz)

            # initialize history on first call
            if self.prevErr is None:
                self.prevErr = errSec
                self.emaErr = errSec

            # update EMA for derivative used by FLL (reduces jitter sensitivity)
            assert self.emaErr is not None
            self.emaErr = (1.0 - self.emaAlpha) * self.emaErr + self.emaAlpha * errSec

            # compute raw and smoothed error deltas
            deltaErrRaw = errSec - self.prevErr
            deltaErrEma = errSec - self.emaErr  # small smoothing → small delay

            # -------- PLL: velocity PI in Hz (uses raw error for minimal delay) --------
            self.freqHz = self.freqHz + self.kpHz * deltaErrRaw + self.kiHz * self.ts * errSec
            justfreqHz = self.freqHz  # for debugging

            # -------- FLL assist: frequency estimate from phase slope --------
            # fractional freq y ≈ -(d phi / dt); with phi=errSec (seconds), dy ≈ -(deltaErr / Ts)
            fracFreq = -(deltaErrEma / self.ts)
            fllHz = self.fllGain * self.f0Hz * fracFreq
            fllHz = self.clamp(fllHz, -self.fllMaxHz, self.fllMaxHz)

            # blend FLL based on phase magnitude (1 at 400 ns, 0 at 20 ns)
            alpha = self.blendAlpha(absErr)
            self.freqHz += alpha * fllHz
#            print(f"freq {justfreqHz:.6f}+{alpha*fllHz:.6f}={self.freqHz:.6f} Hz")

            # -------- convert Hz → DAC codes with sigma-delta on LSBs --------
            targetLsb = self.freqHz / self.hzPerLsb + self.fracLsb
            deltaCode = int(round(targetLsb))
            self.fracLsb = targetLsb - float(deltaCode)

            newCode = self.code + deltaCode

            # -------- clamp and simple anti-windup --------
            if newCode < self.codeMin:
                newCode = self.codeMin
                self.freqHz = (newCode - self.code) * self.hzPerLsb
                self.fracLsb = 0.0
            elif newCode > self.codeMax:
                newCode = self.codeMax
                self.freqHz = (newCode - self.code) * self.hzPerLsb
                self.fracLsb = 0.0

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
#            print(f"PhaseTrack: ffePpbRm15 {ffePpbRm15:8.3f} ", end="")
#        else:
#            print("PhaseTrack: ffePpb      n/a ", end="")
        self.lastPair = pair

        newVal = self.pllWithFll.step(dscDev.toPicoseconds() * 1e-12)
        print(f"errSec {dscDev.toPicoseconds()*1e-12:8e}, code {newVal}")
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
        self.state.dacVal = newVal
        self.dsc.writeDac(newVal)

#        print(f"pairCnt {self.pairCnt:3d}, dscDev {dscDev.elapsedStr()}, "
#              f"adj {adjVal:.1f}, accel {accel:.2f}, newVal {newVal}")
