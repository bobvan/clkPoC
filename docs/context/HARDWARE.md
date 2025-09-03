# Hardware Notes (CM5, F9T, TIC, DAC, GPIO)

## Raspberry Pi CM5
- OS: Debian Bookworm (Raspberry Pi).
- GPIO via **libgpiod**. Install: `sudo apt install gpiod python3-libgpiod`.

### I²C
- Enable I²C (`raspi-config` or edit `/boot/firmware/config.txt`).
- Verify: `i2cdetect -y 1`.

## u-blox F9T
- Connection: `/dev/ttyACM0` (common), 115200 or 460800 baud.
- Messages to enable (UBX):
  - `NAV-PVT` for health & UTC.
  - `TIM-TP` or `TIM-TM2` for timing pulses/marks.
- Use `pyubx2` for parsing; consider `UBX-MON-VER` on startup for sanity.

## Time Interval Counter (TIC)
- Typical: `/dev/ttyUSB0`. Confirm baud/parity/stopbits per model.
- Normalize each measurement to `ppsErrorNs` relative to expected PPS epoch.
- Tag each sample with quality flags from the instrument.

## DAC (I²C)
- Choose: AD5693R/AD5693/AD5680 etc. (12–16 bit typical).
- Keep a single DAC actor with:
  - write queue,
  - clamping,
  - optional rate limiting,
  - optional non-volatile store (if chip supports it).

## GPIO & PPS
- If you tap PPS on a GPIO line (sanity only; TIC is the truth):
  - Request line with edge detection; integrate FD with `loop.add_reader`.
  - Map lines in config: `gpioPpsLine`, `gpioLedLine`.

## Device Paths
- Prefer stable symlinks: `/dev/serial/by-id/...`.
- Optionally add udev rules to create `/dev/f9t` and `/dev/tic`.

## Grounding & Cabling
- Keep TIC and F9T reference grounds clean; avoid ground loops.
- Coax for PPS: 50 Ω, consistent connectors; document cable delays if critical.
