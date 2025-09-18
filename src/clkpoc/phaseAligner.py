from __future__ import annotations


def clamp_int(value: int, lo: int, hi: int) -> int:
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
        f0_hz: float,
        hz_per_lsb: float,
        code_min: int,
        code_max: int,
        code_init: int,
        max_ppb: float,
        goal_ns: float,
        sample_time: float = 1.0,
        hold_count: int = 3,
        correction_fraction: float = 0.05,
    ) -> None:
        if sample_time <= 0.0:
            raise ValueError("sample_time must be positive")
        if max_ppb <= 0.0:
            raise ValueError("max_ppb must be positive")
        if goal_ns <= 0.0:
            raise ValueError("goal_ns must be positive")
        if hold_count < 1:
            raise ValueError("hold_count must be >= 1")
        if not (0.0 < correction_fraction <= 1.0):
            raise ValueError("correction_fraction must be in (0, 1]")

        self.f0_hz = f0_hz
        self.hz_per_lsb = hz_per_lsb
        self.code_min = code_min
        self.code_max = code_max
        self.code = clamp_int(code_init, code_min, code_max)

        self.max_ppb = max_ppb
        self.goal_sec = goal_ns * 1e-9
        self.sample_time = sample_time # XXX get rid of this someday
        self.hold_need = hold_count
        self.correction_fraction = correction_fraction

        self.in_goal = 0
        self.done = False

        # XXX rewrite to use Ts instead of float seconds?
        self.lastErrSec: float | None = None

    def step(self, err_sec: float) -> tuple[int, bool]:
        if self.done:
            return self.code, True

        if abs(err_sec) <= self.goal_sec:
            self.in_goal += 1
        else:
            self.in_goal = 0

        desired_delta = -self.correction_fraction * err_sec
        slope = desired_delta / self.sample_time
        freq_delta_hz = -self.f0_hz * slope

        freq_delta_ppb = (freq_delta_hz / self.f0_hz) * 1e9
        if freq_delta_ppb > self.max_ppb:
            freq_delta_ppb = self.max_ppb
        elif freq_delta_ppb < -self.max_ppb:
            freq_delta_ppb = -self.max_ppb

        freq_delta_hz = self.f0_hz * freq_delta_ppb * 1e-9
        code_delta = freq_delta_hz / self.hz_per_lsb
        self.code = clamp_int(self.code + int(round(code_delta)), self.code_min, self.code_max)

        if self.lastErrSec is not None:
            iffePpb = 1e9 * (err_sec - self.lastErrSec) / self.sample_time
            print(f"PhaseAligner: err {err_sec*1e9:6.1f} ns, "
                f"freq_delta {freq_delta_hz:8.3f} Hz ({freq_delta_ppb:6.3f} ppb), "
                f"code_delta {int(round(code_delta)):6d}, new code {self.code}, iffe {iffePpb:6.3f} ppb")  # noqa: E501
        else:
            print(f"PhaseAligner: err {err_sec*1e9:6.1f} ns, "
                f"freq_delta {freq_delta_hz:8.3f} Hz ({freq_delta_ppb:6.3f} ppb), "
                f"code_delta {int(round(code_delta)):6d}, new code {self.code}")
        self.lastErrSec = err_sec


        if self.in_goal >= self.hold_need:
            self.done = True

        return self.code, self.done
