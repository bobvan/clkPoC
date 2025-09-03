# TODO (initial backlog)

## M0 — Skeleton Running
- [ ] Create venv, install deps (asyncio stdlib, pyserial-asyncio, pyubx2, smbus2, aiosqlite, gpiod).
- [ ] Implement eventBus, tee to storageWriter (stdout only).
- [ ] Add ipcServer (Unix socket) with `getState`.

## M1 — Hardware Readers
- [ ] f9tReader: parse NAV-PVT + TIM-TP (pyubx2), publish `navPvt` and `timTp`.
- [ ] ticReader: parse device frames → `ppsSample` with `ppsErrorNs`.
- [ ] gpioPps: optional PPS edge monitor for sanity.

## M2 — Control Loop
- [ ] Simple PI loop at 1 Hz; gains in config; clamp DAC.
- [ ] Mode machine: idle/disciplining/holdover/fault.
- [ ] Publish `modeChange`, `health`.

## M3 — Storage
- [ ] aiosqlite with WAL; create tables; batch insert.
- [ ] Periodic integrity check; simple `dump` CLI.

## M4 — IPC & UI
- [ ] Extend IPC: `getState`, `setConfig`, `getRecentSamples`.
- [ ] CLI client; later WebSocket for browser UI.

## M5 — Reliability
- [ ] Jittered backoff on serial/I²C errors; auto-recover to previous mode.
- [ ] End-to-end tests with simulators (step, ramp, noise).

## Nice To Have
- [ ] Parquet export for offline analysis.
- [ ] Temperature compensation feedforward (if sensor available).
- [ ] On-device metrics endpoint (Prometheus).
