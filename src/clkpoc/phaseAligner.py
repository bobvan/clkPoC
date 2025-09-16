# XXX rename to coarseAligner.py after testing
# XXX then maybe fineAligner.py for the other one

def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x

class PhaseAligner:
    """
    Aggressive pre-lock aligner for PPS phase.
    Runs for a few seconds right after a known step, then exits when |err| <= goalNs.
    Each call handles one PPS update (Ts=1 s typical).

    Control law (per tick):
      y = sign(err) * min(maxPpb, |err| / tauSec in ppb)
      fHz = f0Hz * y * 1e-9
      deltaCode ≈ fHz / hzPerLsb   (with sigma-delta carry and rate limit)

    Parameters
    ----------
    f0Hz          : nominal oscillator frequency (e.g., 10_000_000.0)
    hzPerLsb      : actuator slope in Hz per DAC code (can be negative)
    codeMin/Max   : DAC rails
    codeInit      : starting DAC code
    tauSec        : target exponential time constant (aggressiveness)
    maxPpb        : hard cap on fractional frequency push (VCO pull limit, in ppb)
    goalNs        : exit threshold on |phase| in ns
    maxCodesPerStep : safety slew limit (codes per PPS)
    holdCount     : require this many consecutive in-goal samples to exit
    """

    def __init__(
        self,
        f0Hz: float,
        hzPerLsb: float,
        codeMin: int,
        codeMax: int,
        codeInit: int,
        tauSec: float = 5.0,
        maxPpb: float = 20.0,
        goalNs: float = 15.0,
        maxCodesPerStep: int = 50,
        sampleTime: float = 1.0,
        holdCount: int = 2
    ) -> None:
        if tauSec <= 0.0:
            raise ValueError("tauSec must be positive")
        if maxPpb <= 0.0:
            raise ValueError("maxPpb must be positive")
        if goalNs <= 0.0:
            raise ValueError("goalNs must be positive")
        if maxCodesPerStep < 1:
            raise ValueError("maxCodesPerStep must be >= 1")
        if sampleTime <= 0.0:
            raise ValueError("sampleTime must be positive")

        self.f0Hz: float = f0Hz
        self.hzPerLsb: float = hzPerLsb
        self.codeMin: int = codeMin
        self.codeMax: int = codeMax
        self.code: int = codeInit

        self.tauSec: float = tauSec
        self.maxPpb: float = maxPpb
        self.goalSec: float = goalNs * 1e-9
        self.ts: float = sampleTime
        self.maxCodesPerStep: int = maxCodesPerStep
        self.holdCountNeed: int = holdCount

        self.fracLsb: float = 0.0
        self.inGoalStreak: int = 0
        self.done: bool = False

    def step(self, errSecRaw: float) -> tuple[int, bool]:
        """
        One PPS update. Returns (newCode, doneFlag).
        errSecRaw should be phase error in seconds (osc - ref), pre-wrapped to (-0.5, 0.5].
        """
        if self.done:
            return self.code, True

        # wrap safety
        errSec = errSecRaw
        while errSec <= -0.5:
            errSec += 1.0
        while errSec > 0.5:
            errSec -= 1.0

        absErr = abs(errSec)

        # in-goal tracking
        if absErr <= self.goalSec:
            self.inGoalStreak += 1
            if self.inGoalStreak >= self.holdCountNeed:
                self.done = True
                return self.code, True
        else:
            self.inGoalStreak = 0

        # choose an aggressive but bounded fractional frequency push (ppb)
        # exponential pull-in with time constant tauSec, capped at maxPpb
        desiredPpb = min(self.maxPpb, (absErr / self.tauSec) * 1e9)
        yPpb = desiredPpb if errSec > 0.0 else -desiredPpb  # positive err → speed up

        # convert to Hz
        fHz = self.f0Hz * yPpb * 1e-9

        # convert Hz to DAC codes, with sigma-delta and slew limit
        targetLsb = fHz / self.hzPerLsb + self.fracLsb
        deltaCode = int(round(targetLsb))

        if deltaCode > self.maxCodesPerStep:
            deltaCode = self.maxCodesPerStep
        elif deltaCode < -self.maxCodesPerStep:
            deltaCode = -self.maxCodesPerStep

        self.fracLsb = targetLsb - float(deltaCode)

        newCode = self.code + deltaCode

        # clamp to rails; drop carry if clamped
        if newCode < self.codeMin:
            newCode = self.codeMin
            self.fracLsb = 0.0
        elif newCode > self.codeMax:
            newCode = self.codeMax
            self.fracLsb = 0.0

        self.code = newCode
        return self.code, False
