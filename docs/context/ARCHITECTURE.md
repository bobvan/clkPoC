# GPSDO Backend Architecture

## Goals
- Event-driven, low-latency control loop with τ0 = 1 second.
- Clear separation of concerns: IO actors, control logic, storage, IPC.
- Deterministic timing: internal monotonic clock for ordering; UTC for user-facing timestamps.
- Easy to test with simulated hardware.

## Runtime Model (asyncio, actors, queues)
Each hardware interface and service runs as an **actor**: a small coroutine with an inbox `asyncio.Queue`. Actors publish **events** and consume **commands**. Use lowerCamelCase for identifiers.

[ f9tReader ] ─┐
[ ticReader ] ─┼─▶ eventBus ──▶ [ controlLoop ] ─▶ [ dacActor ]
[ gpioPps   ] ─┘                  │                  │
├─▶ [ storageWriter ]
└─▶ [ ipcServer ]

- `eventBus`: one shared queue for measurements and state changes.
- `storageWriter`: receives a **tee** of all events for durable logging.
- `ipcServer`: answers UI requests (`getState`, `setConfig`, etc.).

### Time Base
- **Monotonic:** `time.monotonic_ns()` → `tsMonoNs` used for ordering and loop math.
- **UTC:** `tsUtcNs` stored when supplied by F9T (or sampled from system clock when needed).

## Control Loop (1 Hz baseline)
- Input: PPS phase samples from `ticReader` (ns), optional F9T timing messages.
- Output: DAC code updates to steer the OCXO.
- Start simple (PI). Defer Kalman/PLL sophistication until IO proves stable.

## Modes & Transitions (state machine)
- Modes: `idle → disciplining → holdover → fault`.
- Transition signals:
  - `ppsGood` (TIC valid, jitter below threshold) → enter `disciplining`.
  - `ppsLost` (no PPS for N seconds or TIC error) → `holdover`.
  - `recovered` → `disciplining`.
  - `error` → `fault` (requires operator or auto-recover policy).

## IPC & UI
- **Phase 1:** Unix domain socket, newline-delimited JSON; simple request/response.
- **Phase 2:** WebSocket for live updates (FastAPI/Starlette or `websockets`).
- Keep IPC stateless where possible; the backend is source of truth.

## Storage
- SQLite via `aiosqlite`; WAL mode; append-only tables.
- `events` for sparse changes; `samples` for 1 Hz data (or higher if needed).
- Batch writes (e.g., every 100 rows or 250 ms).

### SQLite Schema (initial)
```sql
create table if not exists events(
  id integer primary key,
  tsMonoNs integer not null,
  tsUtcNs integer,
  source text not null,
  kind text not null,
  level integer default 20,
  data text
);
create index if not exists idx_events_ts on events(tsMonoNs);

create table if not exists samples(
  id integer primary key,
  tsMonoNs integer not null,
  tsUtcNs integer,
  ppsErrorNs integer not null,
  dacCode integer,
  tempMilliC integer,
  flags integer default 0
);
create index if not exists idx_samples_ts on samples(tsMonoNs);

Configuration
	•	Pydantic models for validated config: ports, baud, DAC address, gains, thresholds.
	•	Load from JSON/TOML at startup; allow IPC setConfig with validation + persistence.

Testing & Simulation
	•	simF9t, simTic, simDac actors to validate the loop and modes.
	•	pytest-asyncio for end-to-end tests (simulate step/ramp/noise; assert mode transitions).

Deployment
	•	systemd service running the backend inside a venv.
	•	Log to stdout (JSON) → journalctl; periodic export of samples to Parquet (optional).

Failure Policy
	•	Any actor error → publish fault event with details; state machine enters fault.
	•	Auto-restart actors on transient IO errors with jittered backoff.
