from __future__ import annotations


def clampInt(value: int, lo: int, hi: int) -> int:
    return lo if value < lo else hi if value > hi else value


class PhaseAligner:
    """Feedback controller that trims DAC code toward zero phase error.

    Each second we observe the PPS phase error (seconds). We choose a frequency
    correction such that, in the next interval, 5% of the present error would be
    cancelled. The resulting frequency delta is limited to +/-maxPpb and converted
    to DAC codes via hzPerLsb. Once a configurable number of consecutive samples
    land inside goalNs, we report the current code and exit.
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
        holdCount: int = 3,
        corrFracPerStep: float = 0.05,
    ) -> None:
        if maxPpb <= 0.0:
            raise ValueError("maxPpb must be positive")
        if goalNs <= 0.0:
            raise ValueError("goalNs must be positive")
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
        self.holdCount = holdCount
        self.corrFracPerStep = corrFracPerStep

        self.inGoal = 0
        self.done = False

        # XXX rewrite to use Ts instead of float seconds?
        self.lastErrSec: float | None = None

    def step(self, errSec: float) -> tuple[int, bool]:
        if self.done:
            return self.code, True

        if abs(errSec) <= self.goalSec:
            self.inGoal += 1
        else:
            self.inGoal = 0

        desired_delta = -self.corrFracPerStep * errSec
        slope = desired_delta
        freq_delta_hz = -self.f0Hz * slope

        freq_delta_ppb = (freq_delta_hz / self.f0Hz) * 1e9
        if freq_delta_ppb > self.maxPpb:
            freq_delta_ppb = self.maxPpb
        elif freq_delta_ppb < -self.maxPpb:
            freq_delta_ppb = -self.maxPpb

        freq_delta_hz = self.f0Hz * freq_delta_ppb * 1e-9
        code_delta = freq_delta_hz / self.hzPerLsb
        self.code = clampInt(self.code + int(round(code_delta)), self.codeMin, self.codeMax)

        if self.lastErrSec is not None:
            iffePpb = 1e9 * (errSec - self.lastErrSec)
            print(f"PhaseAligner: err {errSec*1e9:6.1f} ns, "
                f"freq_delta {freq_delta_hz:8.3f} Hz ({freq_delta_ppb:6.3f} ppb), "
                f"code_delta {int(round(code_delta)):6d}, new code {self.code}, iffe {iffePpb:6.3f} ppb")  # noqa: E501
        else:
            print(f"PhaseAligner: err {errSec*1e9:6.1f} ns, "
                f"freq_delta {freq_delta_hz:8.3f} Hz ({freq_delta_ppb:6.3f} ppb), "
                f"code_delta {int(round(code_delta)):6d}, new code {self.code}")
        self.lastErrSec = errSec


        if self.inGoal >= self.holdCount:
            self.done = True

        return self.code, self.done
