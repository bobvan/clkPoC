from __future__ import annotations


def clampInt(value: int, lo: int, hi: int) -> int:
    return lo if value < lo else hi if value > hi else value


class PhaseAligner:
    """Feedback controller that trims DAC code toward zero phase error.

    Each second we observe the PPS phase error (seconds). We choose a frequency
    correction such that, in the next interval, 5% of the present error would be
    cancelled. The resulting frequency delta is limited to +/-maxPpb and converted
    to DAC codes via hzPerLsb. Once a configurable number of consecutive samples
    land inside goalNs, we report the current code and exit. Between goalNs and
    errMaxNs we blend fractional frequency and phase corrections to stay inside
    the desired capture range.
    """

    def __init__(
        self,
        f0Hz: float,
        hzPerLsb: float,
        codeMin: int,
        codeMax: int,
        codeInit: int,
        maxPpb: float,
        goalNs: float,
        errMaxNs: float,
        holdCount: int = 3,
        corrFracPerStep: float = 0.05,
    ) -> None:
        if maxPpb <= 0.0:
            raise ValueError("maxPpb must be positive")
        if goalNs <= 0.0:
            raise ValueError("goalNs must be positive")
        if errMaxNs <= goalNs:
            raise ValueError("errMaxNs must be greater than goalNs")
        if holdCount < 1:
            raise ValueError("holdCount must be >= 1")
        if not (0.0 < corrFracPerStep <= 1.0):
            raise ValueError("corrFracPerStep must be in (0, 1]")

        self.f0Hz = f0Hz
        self.hzPerLsb = hzPerLsb
        self.codeMin = codeMin
        self.codeMax = codeMax
        self.code = clampInt(codeInit, codeMin, codeMax)

        self.maxPpb = maxPpb
        self.goalSec = goalNs * 1e-9
        self.errMaxSec = errMaxNs * 1e-9
        self.holdCount = holdCount
        self.corrFracPerStep = corrFracPerStep

        self.inGoal = 0
        self.done = False
        self.freqPpbGain = 1.0 # multiplier for freq correction vs phase correction SWAG
        self.codeDeltaGain = 1.0 # multiplier for code delta SWAG

        # XXX rewrite to use Ts instead of float seconds?
        self.lastErrSec: float | None = None
        self.errSec0: float | None = None
        self.minAbsIffePpb = float('inf')  # track minimum absolute iffePpb
        self.minIffePpbCode = self.code  # and associated code

    def step(self, errSec: float) -> tuple[int, bool]:
        if self.done:
            return self.code, True

        if self.errSec0 is None:
            self.errSec0 = errSec
            # XXX testing
            self.errMaxSec = clampInt(self.errSec0, 0, self.errMaxSec)

        errMag = abs(errSec)

        if errMag <= self.goalSec:
            self.inGoal += 1
        else:
            self.inGoal = 0

        phasePpb = self.corrFracPerStep * errSec * 1e9
        if phasePpb > self.maxPpb:
            phasePpb = self.maxPpb
        elif phasePpb < -self.maxPpb:
            phasePpb = -self.maxPpb

        freqPpb = 0.0
        iffePpb: float | None = None
        if self.lastErrSec is not None:
            iffePpb = 1e9 * (errSec - self.lastErrSec)

            # Track minimum absolute iffePpb and associated code to restore after phase is aligned
            absIffePpb = abs(iffePpb)
            if absIffePpb < self.minAbsIffePpb:
                self.minAbsIffePpb = absIffePpb
                self.minIffePpbCode = self.code

            freqPpb = -self.corrFracPerStep * iffePpb
            if freqPpb > self.maxPpb:
                freqPpb = self.maxPpb
            elif freqPpb < -self.maxPpb:
                freqPpb = -self.maxPpb

        errRange = self.errMaxSec - self.goalSec
        phaseWeight = 1.0
        freqWeight = 0.0
        if errRange > 0.0 and self.lastErrSec is not None:
            weightErr = errMag
            if weightErr < self.goalSec:
                weightErr = self.goalSec
            elif weightErr > self.errMaxSec:
                weightErr = self.errMaxSec

            phaseWeight = (weightErr - self.goalSec) / errRange
            freqWeight = 1.0 - phaseWeight

        combinedPpb = (phaseWeight * phasePpb) + (freqWeight * freqPpb * self.freqPpbGain)
        if combinedPpb > self.maxPpb:
            combinedPpb = self.maxPpb
        elif combinedPpb < -self.maxPpb:
            combinedPpb = -self.maxPpb

        freqDeltaHz = self.f0Hz * combinedPpb * 1e-9
        codeDelta = self.codeDeltaGain * freqDeltaHz / self.hzPerLsb
        newCode = clampInt(self.code + int(round(codeDelta)), self.codeMin, self.codeMax)

        if iffePpb is not None:
            print(
                f"PhaseAligner: err {errSec * 1e9:6.1f} ns, "
                f"combined_ppb {combinedPpb:7.3f} ({phasePpb:5.1f}+{freqPpb*self.freqPpbGain:5.1f}), "
                f"code_delta {int(round(codeDelta)):6d}, new code {newCode}, "
                f"iffe {iffePpb:7.3f} ppb"
            )  # noqa: E501
        else:
            print(
                f"PhaseAligner: err {errSec * 1e9:6.1f} ns, "
                f"combined_ppb {combinedPpb:7.3f} ({phasePpb:5.1f}+{freqPpb*self.freqPpbGain:5.1f}), "
                f"code_delta {int(round(codeDelta)):6d}, new code {newCode}"
            )

        self.code = newCode
        self.lastErrSec = errSec

        if self.inGoal >= self.holdCount:
            self.done = True
            self.code = self.minIffePpbCode
            print(f"PhaseAligner: "
                  f"done, restoring code {self.code} with min iffe {self.minAbsIffePpb:.3f} ppb")

        return self.code, self.done
