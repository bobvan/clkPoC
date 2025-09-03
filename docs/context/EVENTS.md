# Event Schemas (JSON Lines over the bus)

Common envelope (Python dataclass equivalent):

```json
{
  "tsMonoNs": 0,
  "tsUtcNs": null,
  "source": "tic|f9t|dac|gpio|ctrl|ipc|store",
  "kind": "string",
  "data": { "..." : "…" }
}

Measurement Events

tic: ppsSample

Represents one PPS phase measurement from the TIC.

{
  "kind": "ppsSample",
  "data": {
    "ppsErrorNs": 12,
    "quality": "ok|suspect|bad",
    "counterMode": "ti|td|scpi",
    "raw": "optional raw frame or parsed fields"
  }
}

f9t: navPvt

Subset of NAV-PVT needed for health and UTC.

{
  "kind": "navPvt",
  "data": {
    "satUsed": 14,
    "fixType": "3d",
    "utcYear": 2025,
    "utcNs": 1693660800000000000,
    "flags": { "timeOk": true, "raim": true }
  }
}

f9t: timTp or timTm2

Timing pulse or time mark.

{
  "kind": "timTp",
  "data": {
    "riseUtcNs": 1693660800000000000,
    "quantumNs": 1
  }
}

Control & Actuation

ctrl: modeChange

{
  "kind": "modeChange",
  "data": { "from": "idle", "to": "disciplining", "reason": "ppsGood" }
}

ctrl: dacSet

Command issued (or result echoed) to change DAC code.

{
  "kind": "dacSet",
  "data": { "code": 32768, "source": "piController", "ok": true, "error": null }
}

Health & Faults

health: summary

{
  "kind": "health",
  "data": {
    "f9tOk": true,
    "ticOk": true,
    "sat": 14,
    "tempMilliC": 42150
  }
}

fault: error

{
  "kind": "fault",
  "data": {
    "where": "ticReader",
    "what": "readTimeout",
    "detail": "no data for 5 s",
    "action": "autoRetry|halt|degrade"
  }
}

IPC

ipc: configChanged

{
  "kind": "configChanged",
  "data": { "key": "kp", "old": 0.1, "new": 0.12 }
}
