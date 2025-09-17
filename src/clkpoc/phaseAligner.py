# XXX rename to coarseAligner.py after testing
# XXX then maybe fineAligner.py for the other one

from collections import deque


def clampInt(x: int, lo: int, hi: int) -> int:
    return lo if x < lo else hi if x > hi else x

class PhaseAlignerDirect:
    """
    Simple aligner:
      - Drives with fixed ±maxPpb toward zero phase.
      - Estimates frequency from LS slope of recent phase errors.
      - Continuously computes codeZero = code - f_est / hzPerLsb.
      - When |err| <= goal, ramps to codeZero (slew-limited) and exits.

    errSec: phase error in seconds (osc - ref), pre-wrapped to (-0.5, 0.5]
    """

    def __init__(
        self,
        f0Hz: float,
        hzPerLsb: float,      # Hz per DAC LSB (can be negative)
        codeMin: int,
        codeMax: int,
        codeInit: int,
        maxPpb: float = 20.0, # aggressive shove (ppb)
        goalNs: float = 15.0,
        sampleTime: float = 1.0,
        win: int = 7,         # LS window for slope (odd, 5–9 typical)
        holdCount: int = 2,   # consecutive in-band ticks before handoff
        shoveCodesPerStep: int = 50,   # DAC slew during shove
        rampCodesPerStep: int = 25     # DAC slew during final ramp
    ) -> None:
        if win < 3:
            raise ValueError("win must be >= 3")
        if maxPpb <= 0.0 or goalNs <= 0.0 or sampleTime <= 0.0:
            raise ValueError("maxPpb, goalNs, sampleTime must be positive")
        if shoveCodesPerStep < 1 or rampCodesPerStep < 1 or holdCount < 1:
            raise ValueError("slew limits and holdCount must be >= 1")

        self.f0Hz: float = f0Hz
        self.hzPerLsb: float = hzPerLsb
        self.codeMin: int = codeMin
        self.codeMax: int = codeMax
        self.code: int = codeInit

        self.ts: float = sampleTime
        self.maxPpb: float = maxPpb
        self.goalSec: float = goalNs * 1e-9
        self.win: int = win
        self.holdNeed: int = holdCount
        self.shoveCodesPerStep: int = shoveCodesPerStep
        self.rampCodesPerStep: int = rampCodesPerStep

        # history for LS slope
        self.errHist: deque[float] = deque(maxlen=self.win)
        self.codeHist: deque[int] = deque(maxlen=self.win)  # optional log for you
        self.freqEstHz: float = 0.0
        self.codeZero: float | None = None  # continuously updated estimate

        self.inGoalStreak: int = 0
        self.phaseReached: bool = False  # once True, we ramp to codeZero
        self.done: bool = False

    def fitSlopePerSec(self, ys: list[float]) -> float:
        """Least-squares slope dy/dt using x = 0,1,2,..., ts=1s spacing (then scale by ts)."""
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
        slopePerSample = sxy / sxx
        return slopePerSample / self.ts  # seconds per second

    def step(self, errSecRaw: float) -> tuple[int, bool]:
        """
        One PPS update. Returns (newCode, doneFlag).
        """
        if self.done:
            return self.code, True

        # wrap safety
        errSec = errSecRaw
        while errSec <= -0.5:
            errSec += 1.0
        while errSec > 0.5:
            errSec -= 1.0

        # collect histories
        self.errHist.append(errSec)
        self.codeHist.append(self.code)

        # estimate frequency from LS slope of phase
        if len(self.errHist) >= 3:
            slope = self.fitSlopePerSec(list(self.errHist))   # seconds/second
            self.freqEstHz = -self.f0Hz * slope               # Hz
            # compute zero-frequency code from current code and freq estimate
            self.codeZero = float(self.code) - (self.freqEstHz / self.hzPerLsb)

        # goal tracking
        if abs(errSec) <= self.goalSec:
            self.inGoalStreak += 1
        else:
            self.inGoalStreak = 0

        print(f"PhaseAligner: reached {self.phaseReached}, err {errSec*1e9:8.1f} ns, "
              f"f_est {self.freqEstHz:8.1f} Hz, code {self.code:5d}, "
              f"code0 {self.codeZero if self.codeZero is not None else 'N/A':8}")
        if not self.phaseReached:
            # still in shove phase
            yPpb = self.maxPpb if errSec > 0.0 else (-self.maxPpb)  # speed up if late
            fHzCmd = self.f0Hz * yPpb * 1e-9
            desiredDelta = fHzCmd / self.hzPerLsb
            deltaCode = int(round(desiredDelta))
            if deltaCode > self.shoveCodesPerStep:
                deltaCode = self.shoveCodesPerStep
            elif deltaCode < -self.shoveCodesPerStep:
                deltaCode = -self.shoveCodesPerStep
            self.code = clampInt(self.code + deltaCode, self.codeMin, self.codeMax)

            if self.inGoalStreak >= self.holdNeed:
                self.phaseReached = True  # start ramping next tick
            return self.code, False

        # ramp phase: move toward codeZero with a gentle slew, then finish
        if self.codeZero is not None:
            target = int(round(self.codeZero))
            if target > self.code:
                self.code = clampInt(self.code + min(self.rampCodesPerStep, target - self.code),
                    self.codeMin, self.codeMax)
            elif target < self.code:
                self.code = clampInt(self.code - min(self.rampCodesPerStep, self.code - target),
                    self.codeMin, self.codeMax)
            # when close enough, finish
            if abs(self.code - target) <= 1:
                self.code = clampInt(target, self.codeMin, self.codeMax)
                self.done = True
                return self.code, True
            return self.code, False
        else:
            # no estimate yet; just hold for one tick
            self.done = True
            return self.code, True
