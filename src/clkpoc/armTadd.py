"""
Control ARM pin on TADD-2 Mini for Raspberry Pi CM5.

Provides a small helper to initialize BCM GPIO 16 as an output and
issue a 1 ms active-low pulse to trigger the TADD ARM input.

This module tries to import RPi.GPIO. If unavailable (e.g. on non-Pi
development hosts), a minimal in-process mock is used so that code can
be imported and exercised without hardware.
"""

from __future__ import annotations

import logging
import time

try:  # Prefer real GPIO on Raspberry Pi
    import RPi.GPIO as _GPIO  # type: ignore
except Exception:  # Fallback to a minimal mock for non-Pi environments
    class _MockGPIO:  # pragma: no cover - trivial behavior
        BCM = 11
        OUT = 0
        HIGH = 1
        LOW = 0

        def __init__(self) -> None:
            self._mode: int | None = None
            self._state: dict[int, int] = {}
            self._warnings = True

        def setmode(self, mode: int) -> None:
            self._mode = mode

        def getmode(self) -> int | None:
            return self._mode

        def setwarnings(self, flag: bool) -> None:
            self._warnings = flag

        def setup(self, pin: int, mode: int, *, initial: int | None = None) -> None:
            if initial is not None:
                self._state[pin] = initial
            else:
                self._state.setdefault(pin, self.LOW)

        def output(self, pin: int, value: int) -> None:
            self._state[pin] = value
            logging.debug("MockGPIO: pin %s -> %s", pin, value)

    _GPIO = _MockGPIO()  # type: ignore


class ArmTadd:
    """
    Manage Raspberry Pi CM5 BCM GPIO 16 used to ARM the TADD-2 Mini.

    - On initialization: configures GPIO 16 as output and drives it HIGH (inactive).
    - `pulse()`: drives GPIO 16 LOW for 1 ms, then returns it to HIGH.
    """

    _PIN: int = 16  # BCM numbering

    def __init__(self) -> None:
        # Configure GPIO library and pin direction/state
        gpio = _GPIO
        try:
            # Silence warnings about reusing channels
            gpio.setwarnings(False)  # type: ignore[attr-defined]
        except Exception:
            pass

        # Ensure BCM numbering is used, unless already set differently (error).
        try:
            mode = gpio.getmode()  # type: ignore[attr-defined]
        except Exception:
            mode = None
        if mode is None:
            gpio.setmode(gpio.BCM)  # type: ignore[attr-defined]
        elif mode != gpio.BCM:  # type: ignore[attr-defined]
            raise RuntimeError("GPIO mode already set to non-BCM; expected BCM numbering")

        # Initialize pin as an output and drive logic high (inactive)
        gpio.setup(self._PIN, gpio.OUT, initial=gpio.HIGH)  # type: ignore[attr-defined]

        self._gpio = gpio

    def pulse(self) -> None:
        """Drive GPIO 16 LOW for 1 ms, then back to HIGH."""
        print("ArmTadd: resetting")
        self._gpio.output(self._PIN, self._gpio.LOW)
        time.sleep(0.010)
        self._gpio.output(self._PIN, self._gpio.HIGH)

