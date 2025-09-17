# Why is this filename upper case when tic.py and f9t.py aren't?
"""
Control ARM pin on TADD-2 Mini for Raspberry Pi CM5 using libgpiod.

Holding the ARM pin low for more than a second causes the divider to
restart from zer on the next SYNC PPS, which is coming from the GNSS
receiver. This is used to step the phase of the DSC PPS into coarse
alignment with GNSS.

It make take up to four cycles of the nominal 10 MHz disciplined
oscillator frequency, or 400 ns, for the first PPS out of the divider.
Thus DSC PPS will lag GNSS PPS by up to 400 ns after arming.

Provides a small helper to initialize BCM GPIO 16 as an output and
issue an active-low pulse to trigger the TADD ARM input.

This module prefers Python bindings for libgpiod (``import gpiod``) which is
the recommended GPIO interface on Raspberry Pi OS Bookworm and newer. If the
``gpiod`` module is unavailable (e.g. on non-Pi development hosts), a minimal
in-process mock is used so that code can be imported and exercised without
hardware.
"""

from __future__ import annotations

import contextlib
import glob
import logging
import time
from types import TracebackType
from typing import Any, ClassVar

try:  # Prefer libgpiod on Raspberry Pi
    import gpiod as _GPIOD  # type: ignore
except Exception:  # Fallback to a minimal mock for non-Pi environments
    _GPIOD = None  # type: ignore


class _GpioLine:
    """Thin wrapper over libgpiod v1/v2 to drive a single output line.

    If ``gpiod`` is unavailable, falls back to an in-process mock.
    """

    def __init__(self, offset: int, *, consumer: str = "TADD") -> None:
        self._offset = offset
        self._consumer = consumer
        self._mode = "mock"
        self._req: Any | None = None
        self._chip: Any | None = None
        self._line: Any | None = None
        self._state = 1  # track last value for mock

        if _GPIOD is None:
            logging.info("TADD: using Mock GPIO (gpiod not available)")
            return

        try:
            # Detect libgpiod v2 (has request_lines) vs v1
            if hasattr(_GPIOD, "request_lines"):
                # v2 API — try all gpiochips until one accepts the offset
                self._mode = "v2"
                assert _GPIOD is not None
                settings = _GPIOD.LineSettings(
                    direction=_GPIOD.line.Direction.OUTPUT,
                    output_value=_GPIOD.line.Value.ACTIVE,  # start HIGH
                )
                last_err: Exception | None = None
                for chip_path in sorted(glob.glob("/dev/gpiochip*")):
                    try:
                        req = _GPIOD.request_lines(
                            chip_path,
                            consumer=consumer,
                            config={offset: settings},
                        )
                        self._req = req
                        self._state = 1
                        logging.info("TADD: using %s for GPIO%d", chip_path, offset)
                        break
                    except Exception as e:  # try next chip
                        last_err = e
                        continue
                if self._req is None:
                    raise RuntimeError(str(last_err or "no gpiochip accepted offset"))
            else:
                # v1 API — try all gpiochips and request if offset is in range
                self._mode = "v1"
                last_err: Exception | None = None
                for chip_dev in sorted(glob.glob("/dev/gpiochip*")):
                    try:
                        chip: Any = _GPIOD.Chip(chip_dev)
                        try:
                            if hasattr(chip, "num_lines"):
                                num: int = int(chip.num_lines())
                                if offset >= num:
                                    chip.close()
                                    continue
                            line: Any = chip.get_line(offset)
                            req_type: Any = getattr(_GPIOD, "LINE_REQ_DIR_OUT", 1)
                            line.request(
                                consumer=consumer,
                                type=req_type,
                                default_val=1,
                            )
                            self._chip = chip
                            self._line = line
                            self._state = 1
                            logging.info("TADD: using %s for GPIO%d", chip_dev, offset)
                            break
                        except Exception as e:
                            last_err = e
                            with contextlib.suppress(Exception):
                                chip.close()
                            continue
                    except Exception as e:
                        last_err = e
                        continue
                if self._line is None:
                    raise RuntimeError(str(last_err or "no gpiochip accepted offset"))
        except Exception as e:  # pragma: no cover - hardware/env dependent
            logging.warning("TADD: failed to init gpiod, using mock: %s", e)
            self._mode = "mock"

    def set_value(self, val: int) -> None:
        self._state = 1 if val else 0
        if self._mode == "v2":  # pragma: no cover - hardware/env dependent
            try:
                req = self._req
                if req is not None:
                    mod = _GPIOD
                    if mod is not None:
                        req.set_value(
                            self._offset,
                            mod.line.Value.ACTIVE if val else mod.line.Value.INACTIVE,
                        )
            except Exception as e:
                logging.warning("TADD: gpiod v2 set_value failed: %s", e)
        elif self._mode == "v1":  # pragma: no cover - hardware/env dependent
            try:
                line = self._line
                if line is not None:
                    line.set_value(val)
            except Exception as e:
                logging.warning("TADD: gpiod v1 set_value failed: %s", e)
        else:
            logging.debug("MockGPIO: line %s -> %s", self._offset, val)

    def close(self) -> None:
        if self._mode == "v2":  # pragma: no cover - hardware/env dependent
            with contextlib.suppress(Exception):
                req = self._req
                if req is not None:
                    req.release()  # type: ignore[attr-defined]
        elif self._mode == "v1":  # pragma: no cover - hardware/env dependent
            with contextlib.suppress(Exception):
                line = self._line
                if line is not None:
                    line.release()
            with contextlib.suppress(Exception):
                chip = self._chip
                if chip is not None:
                    chip.close()

    def __del__(self):  # pragma: no cover - best-effort cleanup
        try:
            self.close()
        except Exception:
            pass


class TADD:
    """
    Manage Raspberry Pi CM5 BCM GPIO 16 used to ARM the TADD-2 Mini.

    - On initialization: configures GPIO 16 as output and drives it HIGH (inactive).
    - `pulse()`: drives GPIO 16 LOW for 1 ms, then returns it to HIGH.
    """

    _PIN: int = 16  # BCM numbering (line offset on gpiochip0)
    _shared_line: ClassVar[_GpioLine | None] = None

    def __init__(self) -> None:
        # Initialize once per process and reuse the same requested line.
        # This avoids leaking multiple requests and hitting EBUSY on re-instantiation.
        if TADD._shared_line is None:
            TADD._shared_line = _GpioLine(self._PIN)
        assert TADD._shared_line is not None
        self._line: _GpioLine = TADD._shared_line

    def pulse(self) -> None:
        """Drive ARM pin LOW for 1 second or more per manual, then back to HIGH."""
        self._line.set_value(0)
        time.sleep(1.1)
        self._line.set_value(1)

    @classmethod
    def close(cls) -> None:
        """Release the shared GPIO line if held."""
        if cls._shared_line is not None:
            cls._shared_line.close()
            cls._shared_line = None

    def __enter__(self) -> TADD:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Intentionally do not auto-close to preserve shared singleton semantics.
        # Call TADD.close() explicitly at shutdown if needed.
        pass

# Ensure GPIO line is released when the process exits
try:
    import atexit as _atexit  # late import to avoid unused import if not needed

    _atexit.register(TADD.close)
except Exception:
    # Best-effort; safe to ignore if registration fails
    pass
