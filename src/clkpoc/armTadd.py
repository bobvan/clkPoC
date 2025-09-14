"""
Control ARM pin on TADD-2 Mini for Raspberry Pi CM5 using libgpiod.

Provides a small helper to initialize BCM GPIO 16 as an output and
issue an active-low pulse to trigger the TADD ARM input.

This module prefers Python bindings for libgpiod (``import gpiod``) which is
the recommended GPIO interface on Raspberry Pi OS Bookworm and newer. If the
``gpiod`` module is unavailable (e.g. on non-Pi development hosts), a minimal
in-process mock is used so that code can be imported and exercised without
hardware.
"""

from __future__ import annotations

import logging
import contextlib
import glob
import os
import time

try:  # Prefer libgpiod on Raspberry Pi
    import gpiod as _GPIOD  # type: ignore
except Exception:  # Fallback to a minimal mock for non-Pi environments
    _GPIOD = None  # type: ignore


class _GpioLine:
    """Thin wrapper over libgpiod v1/v2 to drive a single output line.

    If ``gpiod`` is unavailable, falls back to an in-process mock.
    """

    def __init__(self, offset: int, *, consumer: str = "ArmTadd") -> None:
        self._offset = offset
        self._consumer = consumer
        self._mode = "mock"
        self._req = None
        self._chip = None
        self._line = None
        self._state = 1  # track last value for mock

        if _GPIOD is None:
            logging.info("ArmTadd: using Mock GPIO (gpiod not available)")
            return

        try:
            # Detect libgpiod v2 (has request_lines) vs v1
            if hasattr(_GPIOD, "request_lines"):
                # v2 API — try all gpiochips until one accepts the offset
                self._mode = "v2"
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
                        logging.info("ArmTadd: using %s for GPIO%d", chip_path, offset)
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
                        chip = _GPIOD.Chip(chip_dev)
                        try:
                            if hasattr(chip, "num_lines"):
                                num = chip.num_lines()
                                if offset >= num:
                                    chip.close()
                                    continue
                            line = chip.get_line(offset)
                            line.request(
                                consumer=consumer,
                                type=_GPIOD.LINE_REQ_DIR_OUT,
                                default_val=1,
                            )
                            self._chip = chip
                            self._line = line
                            self._state = 1
                            logging.info("ArmTadd: using %s for GPIO%d", chip_dev, offset)
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
            logging.warning("ArmTadd: failed to init gpiod, using mock: %s", e)
            self._mode = "mock"

    def set_value(self, val: int) -> None:
        self._state = 1 if val else 0
        if self._mode == "v2":  # pragma: no cover - hardware/env dependent
            try:
                self._req.set_value(
                    self._offset,
                    _GPIOD.line.Value.ACTIVE if val else _GPIOD.line.Value.INACTIVE,
                )
            except Exception as e:
                logging.warning("ArmTadd: gpiod v2 set_value failed: %s", e)
        elif self._mode == "v1":  # pragma: no cover - hardware/env dependent
            try:
                self._line.set_value(val)
            except Exception as e:
                logging.warning("ArmTadd: gpiod v1 set_value failed: %s", e)
        else:
            logging.debug("MockGPIO: line %s -> %s", self._offset, val)

    def close(self) -> None:
        if self._mode == "v2":  # pragma: no cover - hardware/env dependent
            with contextlib.suppress(Exception):
                self._req.release()  # type: ignore[attr-defined]
        elif self._mode == "v1":  # pragma: no cover - hardware/env dependent
            with contextlib.suppress(Exception):
                self._line.release()
            with contextlib.suppress(Exception):
                self._chip.close()

    def __del__(self):  # pragma: no cover - best-effort cleanup
        try:
            self.close()
        except Exception:
            pass


class ArmTadd:
    """
    Manage Raspberry Pi CM5 BCM GPIO 16 used to ARM the TADD-2 Mini.

    - On initialization: configures GPIO 16 as output and drives it HIGH (inactive).
    - `pulse()`: drives GPIO 16 LOW for 1 ms, then returns it to HIGH.
    """

    _PIN: int = 16  # BCM numbering (line offset on gpiochip0)

    def __init__(self) -> None:
        # Initialize GPIO line as an output and drive logic high (inactive)
        self._line = _GpioLine(self._PIN)

    def pulse(self) -> None:
        """Drive GPIO 16 LOW briefly, then back to HIGH."""
        self._line.set_value(0)
        time.sleep(0.110)
        self._line.set_value(1)
