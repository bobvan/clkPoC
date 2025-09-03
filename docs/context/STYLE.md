Naming & Types
	•	All field names are lowerCamelCase.
	•	Durations and timestamps are integers in ns.
	•	Avoid floats in persistent logs; if needed, store scaled integers or strings.

---

# Code Style & Conventions

## Naming
- **lowerCamelCase** for functions, variables, attributes: `f9tReader`, `dacActor`, `nowNs`.
- **PascalCase** for classes and Enums: `GpsdoModes`, `Mode`, `Registry`.
- **No underscores** in identifiers (Python snake_case disabled by choice).

## Typing & Structure
- Use Python 3.12+, type hints everywhere.
- Small modules by actor/service: `actors/f9t.py`, `actors/tic.py`, `actors/dac.py`, `services/ipc.py`, `services/storage.py`, `control/loop.py`.
- Dataclasses or Pydantic models for events and config.

## Async Patterns
- One `asyncio.Queue` per actor; do not block the event loop.
- Wrap blocking IO (`smbus2`, some serial ops) with `asyncio.to_thread`.
- Use `loop.add_reader(fd, callback)` for GPIO edge FDs.

## Errors & Retries
- Short retries with jittered backoff inside the actor; publish `fault` events on escalation.
- Never swallow exceptions silently; log with context.

## Logging
- JSON to stdout. Include: `tsMonoNs`, `source`, `kind`, and `data`.
- Keep messages small; avoid dumping megabyte frames.

## Config
- Pydantic models; validate on load and on IPC updates.
- Store a single `config.json` in the repo or `/etc/gpsdo/config.json`.

## Lint & Format
- Black for formatting, Ruff for linting; allow camelCase.
- `pyproject.toml`:
```toml
[tool.ruff]
select = ["E","F","I","UP","B"]
ignore = ["N802","N803","N806"]  # allow non-snake-case names

[tool.black]
line-length = 100

Testing
	•	pytest-asyncio for async tests.
	•	Provide simulators for F9T/TIC/DAC so tests don’t touch hardware.

Docstrings
	•	Concise, imperative style. Include units for any numeric parameter (e.g., ns, Hz).

---
