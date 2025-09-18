# AGENTS.md

## Code style

- Python: use type hints everywhere; assume pyright strict.
- Prefer camelCase (avoid underscores) in identifiers.
- Avoid deprecated typing aliases; use built-ins (list, tuple, collections.deque).

## Project rules

- Assume tau0 = 1 in timing code.
- When editing tests, keep pytest discovery compatible with test*.py.

## Verification

- Run: ruff check && pyright && pytest -q
- Fail the task if any of the above are non-zero.

## PI Control

- Assume f0Hz is 10 MHz
- Assume sample_time is 1 second

## Timestamnp Details

- Paired timestamps are always from the same UTC second
- Never any need to unwrap
- Resolution is picoseconds, but accuracy is only about 60 ps
