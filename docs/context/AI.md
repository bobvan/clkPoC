# AI Playbook for This Repo

**Goal:** Make AI edits safe, consistent, and fast for a headless Raspberry Pi CM5 GPSDO project.

## Project Ground Rules (AI must follow)

- **Naming:** lowerCamelCase for everything; PascalCase for classes/enums. **No underscores.**
- **Time:** use `time.monotonic_ns()` for ordering/calculations; store UTC as `tsUtcNs` when available.
- **Units:** timestamps, durations, errors → **integers in ns** (no floats in persistence).
- **Concurrency:** asyncio everywhere; no blocking in the event loop. Wrap blocking IO in `asyncio.to_thread(...)`.
- **Actors:** one queue per actor; event bus publishes structured events (see `/docs/context/EVENTS.md`).
- **State machine:** `idle → disciplining → holdover → fault` with explicit event-driven transitions.
- **Logging:** JSON to stdout with `tsMonoNs`, `source`, `kind`, `data`.
- **Storage:** SQLite via `aiosqlite` in WAL mode; batch inserts; stable schema in `/docs/context/ARCHITECTURE.md`.
- **Diff discipline:** produce cohesive, minimal diffs with tests and docstrings; do not change schemas casually.

> If an edit needs to change an event schema or public IPC, the AI must propose a migration plan first.

---

## How to Prime the IDE AI

- **Open these files/tabs before asking for edits:**  
  `docs/context/ARCHITECTURE.md`, `docs/context/EVENTS.md`, `docs/context/STYLE.md`, `docs/context/HARDWARE.md`, relevant `actors/*.py`, `control/loop.py`, `services/*.py`.
- **Keep a short “work request” file open** (e.g., `WORK_NOTE.md`) with your exact task and acceptance criteria. The AI will read it.
- **Pin constraints**: “no underscores”, “ns only”, “async only”, “τ0 = 1 s baseline”.

---

## Reusable System Prompt (paste into your AI chat once per session)

> You are editing a Python asyncio GPSDO backend running on a Raspberry Pi CM5. Follow `/docs/context/*`. Use lowerCamelCase identifiers (no underscores). Use `time.monotonic_ns()` internally; store UTC if provided by F9T. Events and IPC must match `/docs/context/EVENTS.md`. Implement actors with queues, avoid blocking the event loop, wrap I²C/serial blocking calls in `asyncio.to_thread`. Persist to SQLite via `aiosqlite` in WAL mode, batching writes. Provide small, cohesive diffs with tests and docstrings. If changing public schemas or IPC, propose a migration plan first.

---

## Copilot Chat / *Edits* Prompts

### 1) Add a new actor (template)

@workspace /edit
Create actors/tempSensor.py that reads a temperature in milliC every 1 s and emits a
health event with tempMilliC. Integrate it into main startup, add config keys, and
batch persistence in storageWriter. Respect lowerCamelCase, asyncio, and event schemas.
Add unit tests with pytest-asyncio using a simulator actor. Do not block the event loop.

### 2) Implement F9T UBX parsing (pyubx2 + serial_asyncio)

@workspace /edit
In actors/f9t.py, implement an asyncio reader using serial_asyncio. Parse UBX NAV-PVT and
TIM-TP with pyubx2 and publish navPvt and timTp events as defined in EVENTS.md.
Run blocking parser parts in to_thread if needed. Add retries with jittered backoff.
Update HARDWARE.md with enabled messages. Add tests with a simulated UBX stream.

### 3) DAC actor (smbus2)

@workspace /edit
In actors/dac.py, implement a dacActor that accepts {“op”:“setCode”,“code”:int}. Use smbus2
wrapped in asyncio.to_thread. Clamp to 0..65535, add simple rate limiting (max 2 writes/s)
and retries. Emit dacSet events with ok/error. Update controlLoop to send setCode only
when code changes. Include unit tests that monkeypatch I²C calls.

### 4) State machine wiring with transitions

@workspace /edit
Add a GpsdoModes AsyncMachine with states idle, disciplining, holdover, fault. Add transitions
ppsGood, ppsLost, recovered, error. Drive transitions in controlLoop based on ppsSample quality
and missing PPS timers. Emit modeChange events on transitions. Provide tests covering each path.

### 5) IPC endpoint for recent samples

@workspace /edit
Extend services/ipc.py with a “getRecentSamples” request taking limit. Query SQLite using
aiosqlite and return rows (tsMonoNs, ppsErrorNs, dacCode, tempMilliC, flags) in JSON lines.
Enforce limit<=3600. Add tests using a temp DB and fixtures.

### 6) Non-blocking sweep: detect and fix blocking calls

@workspace /edit
Scan the repo for potential blocking calls in async contexts (I²C, serial, sqlite) and refactor
to use asyncio.to_thread or connection pools as needed. Add a CI check that greps for known
blocking calls in async functions and flags them in tests.

---

## Zed Agent Prompts

**Repo-wide refactor (camelCase enforcement)**

Refactor any remaining snake_case names to lowerCamelCase without changing public schemas
or filenames. Update references across files. Run ruff config from STYLE.md to ignore N802/N803/N806.
Provide a single cohesive diff and a brief summary.

**Agentic plan before editing**

Propose an edit plan to implement a PI controller with kp, ki from config, acting at 1 Hz
on ppsErrorNs to produce dacCode updates. Include guardrails for holdover and fault modes.
After I approve, perform the edit with tests and docstrings.

---

## Cursor / Windsurf Prompts

**Multi-file feature**

Implement a Unix domain socket IPC request “setConfig” that accepts a JSON object,
validates with pydantic models, persists to config.json, and emits an ipc:configChanged event.
Add unit tests. Follow STYLE.md and EVENTS.md strictly.

**Safety check**

List any places where float math could leak into persistent storage or event payloads.
Replace with integer ns or scaled integers. Provide a small diff with tests.

---

## PR Checklist (AI + human)

- [ ] Identifiers are lowerCamelCase; no underscores snuck in.
- [ ] No blocking calls in async functions; any blocking I/O is wrapped in `to_thread`.
- [ ] Event and IPC schemas match `/docs/context/EVENTS.md`.
- [ ] Logging to stdout is JSON and includes `tsMonoNs`, `source`, `kind`.
- [ ] SQLite writes are batched; WAL enabled; indexes match ARCHITECTURE.md.
- [ ] Unit tests added or updated; simulators used where hardware is involved.
- [ ] Docstrings include units and rationale; HARDWARE.md updated if needed.
- [ ] Migration note present if any public contract changed (prefer not).

---

## Common “Do / Don’t” for the AI

**Do**
```python
# good: wrap blocking I²C
await asyncio.to_thread(dacWriteCode, code)

Don’t

# bad: blocking call inside async function
smbus.write_i2c_block_data(addr, reg, data)  # <-- wrap in to_thread

Do

# good: ns integers
tsMonoNs = time.monotonic_ns()
ppsErrorNs = int(deltaNs)

Don't

# bad: floats in persisted data
pps_error = 0.123456  # <-- store scaled integer instead

Handy One-liners for the AI to insert
	•	Enable SQLite WAL:

await db.execute("pragma journal_mode=wal;")
await db.execute("pragma synchronous=normal;")

	•	Jittered backoff:
delay = min(5.0, base * (1.5 ** tries)) + random.random()*0.2

	•	Queue drain with backpressure awareness:

if queue.full():
    _ = queue.get_nowait()
    queue.task_done()
await queue.put(ev)

When the AI Should Ask First (and propose a plan)
	•	Changing event/IPC schemas.
	•	Touching the control loop math beyond PI tuning.
	•	Altering storage schema or indexes.
	•	Adding new long-running background tasks.

Keep edits scoped, reviewed, and tested.
