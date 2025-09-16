
from collections import deque

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
        self.pllWithFllSafe = self.PllWithFllSafe(hzPerLsb = -4.2034700315e-05,
            codeMin=11400, codeMax=15000, codeInit=self.state.dacVal)

    class PllWithFllSafe:
        def __init__(
            self,
            hzPerLsb: float,
            codeMin: int,
            codeMax: int,
            codeInit: int,
            f0Hz: float = 10e6,
            sampleTime: float = 1.0,
            # PLL bandwidths
            trackBandHz: float = 0.05,
            acquireBandHz: float = 0.10,
            zeta: float = 0.7,
            # FLL engage window
            engageHighNs: float = 400.0,
            engageLowNs: float = 20.0,
            # FLL strength and limits
            fllGain: float = 0.4,
            fllMaxHz: float = 5e-4,   # keep small; raise after stable
            # Global freq clamp and DAC slew limit
            maxAbsFreqHz: float = 0.005,
            maxCodesPerStep: int = 10,
            # Error polarity: +1 if err=osc-ref, -1 if err=ref-osc
            errorPolarity: int = +1,
            # Holdoff after zero-crossing (seconds)
            zeroHoldSteps: int = 3,
            slopeWin: int = 10,
            deadbandNs: float = 50.0,
            # Debug controls
            debug: bool = True,
            debugEvery: int = 1,
        ) -> None:
            self.f0Hz: float = f0Hz
            self.hzPerLsb: float = hzPerLsb
            self.codeMin: int = codeMin
            self.codeMax: int = codeMax
            self.code: int = codeInit

            self.ts: float = sampleTime
            self.zeta: float = zeta
            self.trackBandHz: float = trackBandHz
            self.acquireBandHz: float = acquireBandHz

            self.engageHighSec: float = engageHighNs * 1e-9
            self.engageLowSec: float = engageLowNs * 1e-9

            self.fllGain: float = fllGain
            self.fllMaxHz: float = fllMaxHz
            self.maxAbsFreqHz: float = maxAbsFreqHz
            self.maxCodesPerStep: int = max(1, maxCodesPerStep)

            self.errorPolarity: int = 1 if errorPolarity >= 0 else -1
            self.zeroHoldSteps: int = max(0, zeroHoldSteps)
            self.zeroHoldCounter: int = 0

            # Controller state
            self.freqHz: float = 0.0
            self.prevErr: float | None = None
            self.prevErrSign: int = 0
            self.fracLsb: float = 0.0

            # Derivative using median-of-3 to reduce spikes
            self.errWindow: deque[float] = deque(maxlen=3)

            # Start in acquire bandwidth
            self.kpHz: float = 0.0
            self.kiHz: float = 0.0
            self.useAcquire: bool = True
            self.setPllBandwidth(self.acquireBandHz)
            self.slopeWin: int = max(3, slopeWin)
            self.deadbandSec: float = deadbandNs * 1e-9
            self.errHist: deque[float] = deque(maxlen=self.slopeWin)

            # Debug
            self.debug = debug
            self.debugEvery = max(1, debugEvery)
            self.stepCount: int = 0

        def sgn(self, x: float) -> int:
            return 0 if x == 0.0 else (1 if x > 0.0 else -1)


        def fitSlope(self, ys: list[float]) -> float:
            # returns dy/dt (seconds per second) using LS fit; sample times are 0,1,2,..., (Ts=1 s)
            n = len(ys)
            if n < 2:
                return 0.0
            xMean = (n - 1) / 2.0
            yMean = sum(ys) / float(n)
            sxx = 0.0
            sxy = 0.0
            for i, y in enumerate(ys):
                dx = i - xMean
                dy = y - yMean
                sxx += dx * dx
                sxy += dx * dy
            if sxx == 0.0:
                return 0.0
            slopePerSample = sxy / sxx              # seconds error change per sample
            return slopePerSample / self.ts         # seconds per second

        def fllBlendQuadratic(self, absErr: float) -> float:
            # quadratic taper: 1 at high, 0 at low, faster fade near low
            if absErr >= self.engageHighSec:
                return 1.0
            if absErr <= self.engageLowSec:
                return 0.0
            x = (absErr - self.engageLowSec) / (self.engageHighSec - self.engageLowSec)
            return x * x

        def clamp(self, x: float, lo: float, hi: float) -> float:
            return lo if x < lo else hi if x > hi else x

        def setPllBandwidth(self, bandHz: float) -> None:
            omega = 2.0 * 3.141592653589793 * bandHz
            self.kpHz = 2.0 * self.zeta * omega
            self.kiHz = omega * omega

        def fllBlend(self, absErr: float) -> float:
            if absErr >= self.engageHighSec:
                return 1.0
            if absErr <= self.engageLowSec:
                return 0.0
            return (absErr - self.engageLowSec) / (self.engageHighSec - self.engageLowSec)

        def median3(self, a: float, b: float, c: float) -> float:
            return a + b + c - min(a, b, c) - max(a, b, c)

        def step(self, errSecRaw: float) -> int:
            self.stepCount += 1
            # Wrap and apply polarity so controller sees err = osc - ref
            errSec = errSecRaw
            while errSec <= -0.5:
                errSec += 1.0
            while errSec > 0.5:
                errSec -= 1.0
            errSec *= self.errorPolarity

            absErr = abs(errSec)

            # Bandwidth scheduling with simple hysteresis (±20% around engageLowSec)
            lowHi = self.engageLowSec * 1.2
            lowLo = self.engageLowSec * 0.8
            if self.useAcquire and absErr <= lowLo:
                self.useAcquire = False
                self.setPllBandwidth(self.trackBandHz)
            elif not self.useAcquire and absErr >= lowHi:
                self.useAcquire = True
                self.setPllBandwidth(self.acquireBandHz)

            # First sample init
            if self.prevErr is None:
                self.prevErr = errSec
                self.prevErrSign = 0 if errSec == 0.0 else (1 if errSec > 0.0 else -1)
                self.errWindow.extend([errSec, errSec, errSec])

            assert self.prevErr is not None

            # Median-of-3 derivative for FLL
            self.errWindow.append(errSec)
            e0, e1, e2 = list(self.errWindow)
            eMed = self.median3(e0, e1, e2)
            # approx derivative over one step using median-smoothed error
            deltaErrFll = eMed - (self.prevErr if len(self.errWindow) < 3 else self.median3(e0, e0, e1))

            # Raw derivative for PLL (minimal delay)
            deltaErrPll = errSec - self.prevErr

            # keep updating histories
            self.errHist.append(errSec)

            # -------- PLL (velocity PI) --------
            pllBefore = self.freqHz
            self.freqHz = self.freqHz + self.kpHz * deltaErrPll + self.kiHz * self.ts * errSec

            # ---- FLL assist (robust) ----
            absErr = abs(errSec)

            # deadband: fully disable FLL near zero phase
            if absErr <= self.deadbandSec:
                fllHzRaw = 0.0
                fllGate = 0.0
                fllHz = 0.0
            else:
                # LS slope over last N points (seconds/second). de/dt = f_osc - f_ref (fractional w.r.t 1 Hz)
                # FLL command should oppose measured freq error: delta_f ≈ -K * de/dt
                slope = self.fitSlope(list(self.errHist))
                fllHzRaw = -self.fllGain * self.f0Hz * slope

                # Let FLL act on measured frequency error (slope) only; gating handles phase magnitude

                # cap the shove and apply quadratic magnitude gating
                fllHz = self.clamp(fllHzRaw, -self.fllMaxHz, self.fllMaxHz)
                fllGate = self.fllBlendQuadratic(absErr)
                fllHz *= fllGate

            # zero-crossing holdoff (keep if you like it; optional with deadband+quadratic)
            if self.prevErr is not None:
                prevSign = 0 if self.prevErr == 0.0 else (1 if self.prevErr > 0.0 else -1)
                curSign = 0 if errSec == 0.0 else (1 if errSec > 0.0 else -1)
                if prevSign != 0 and curSign != 0 and prevSign != curSign:
                    fllHz = 0.0  # one-shot blank on the crossing

            # sum PLL + gated FLL and clamp overall frequency command
            sumBeforeClamp = self.freqHz + fllHz
            self.freqHz = self.clamp(sumBeforeClamp, -self.maxAbsFreqHz, self.maxAbsFreqHz)

            # Convert Hz → DAC steps with sigma-delta and slew limit
            cmdLsb = self.freqHz / self.hzPerLsb
            targetLsb = cmdLsb + self.fracLsb
            deltaCodeDesired = int(round(targetLsb))
            # per-step slew limiting
            deltaCode = deltaCodeDesired
            rateLimited = False
            if deltaCode > self.maxCodesPerStep:
                deltaCode = self.maxCodesPerStep
                rateLimited = True
            elif deltaCode < -self.maxCodesPerStep:
                deltaCode = -self.maxCodesPerStep
                rateLimited = True
            # Update fractional accumulator; when rate-limited, prevent huge residuals
            if rateLimited:
                self.fracLsb = 0.0
            else:
                self.fracLsb = targetLsb - float(deltaCode)

            newCode = self.code + deltaCode
            clamped = False
            if newCode < self.codeMin:
                newCode = self.codeMin
                clamped = True
                self.fracLsb = 0.0
            elif newCode > self.codeMax:
                newCode = self.codeMax
                clamped = True
                self.fracLsb = 0.0

            appliedDelta = newCode - self.code
            self.code = newCode

            # Do NOT force controller state to the applied step; avoid quantizer lock-in

            # tiny leak when clamped to prevent building a huge integrator state
            if clamped:
                self.freqHz *= 0.8  # leak 20%; adjust 0.7..0.95 if needed

            # Debug print
            if hasattr(self, 'debug') and self.debug and (self.stepCount % self.debugEvery == 0):
                errSign = self.sgn(errSec)
                desiredDeltaCodeSign = -errSign * self.sgn(self.hzPerLsb)
                actualDeltaCodeSign = self.sgn(float(deltaCode))
                # Build FLL fields safely if we were in deadband
                slope_str = 'nan' if absErr <= self.deadbandSec else f'{slope:+.3e}'
                fllRaw_str = '0.0' if absErr <= self.deadbandSec else f'{fllHzRaw:+.3e}'
                gate_str = '0.00' if absErr <= self.deadbandSec else f'{fllGate:.2f}'
                print(
                    f"e={errSec:+.3e} abs={absErr:.3e} sgn={errSign:+d} | "
                    f"PLL:kp={self.kpHz:.3e} ki={self.kiHz:.3e} useAcq={self.useAcquire} "
                    f"pllBefore={pllBefore:+.3e} dEpll={deltaErrPll:+.3e} | "
                    f"FLL:slope={slope_str} raw={fllRaw_str} gate={gate_str} fll={fllHz:+.3e} | "
                    f"sumCmd={sumBeforeClamp:+.3e} freqHz={self.freqHz:+.3e} clamp={'Y' if clamped else 'N'} rateLim={'Y' if 'rateLimited' in locals() and rateLimited else 'N'} | "
                    f"hz/LSB={self.hzPerLsb:+.3e} cmdLsb={cmdLsb:+.2f} frac={self.fracLsb:+.2f} "
                    f"Δcode={deltaCode:+d} applΔ={appliedDelta:+d} code={self.code} | "
                    f"desiredΔcodeSign={desiredDeltaCodeSign:+d} actualΔcodeSign={actualDeltaCodeSign:+d}"
                )

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

        newVal = self.pllWithFllSafe.step(dscDev.toPicoseconds() * 1e-12)
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
