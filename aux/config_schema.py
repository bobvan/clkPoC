from __future__ import annotations

import os
import shutil
import tempfile
from typing import Any, Callable

from pydantic import BaseModel, ValidationError
from ruamel.yaml import YAML

try:
    from filelock import FileLock
except Exception:
    FileLock = None  # optional

CURRENT_SCHEMA_VERSION = 3

class Config(BaseModel):
    # keep field names in lowerCamelCase (no underscores)
    schemaVersion: int = CURRENT_SCHEMA_VERSION

    # hardware
    f9tPort: str = "/dev/ttyACM0"
    f9tBaud: int = 115200
    ticPort: str = "/dev/ttyUSB0"
    ticBaud: int = 115200
    dacAddress: int = 0x4C
    gpioPpsLine: int | None = None

    # control loop (τ0 = 1 s baseline)
    kp: float = 0.10
    ki: float = 0.02
    dacMin: int = 0
    dacMax: int = 65535

    # misc
    logLevel: str = "INFO"
    notes: str | None = None

def yamlLoader():
    y = YAML(typ="rt")  # round-trip preserves comments & ordering
    y.indent(mapping=2, sequence=2, offset=2)
    return y

# --------- migrations ---------
def migrateV1ToV2(doc: dict[str, Any]) -> dict[str, Any]:
    # Example changes:
    # - gpsPort -> f9tPort
    # - serialBaud -> f9tBaud
    # - dacAddr -> dacAddress
    if "gpsPort" in doc and "f9tPort" not in doc:
        doc["f9tPort"] = doc.pop("gpsPort")
    if "serialBaud" in doc and "f9tBaud" not in doc:
        doc["f9tBaud"] = doc.pop("serialBaud")
    if "dacAddr" in doc and "dacAddress" not in doc:
        doc["dacAddress"] = doc.pop("dacAddr")

    # Introduce control gains if missing
    doc.setdefault("kp", 0.10)
    doc.setdefault("ki", 0.02)

    doc["schemaVersion"] = 2
    return doc

def migrateV2ToV3(doc: dict[str, Any]) -> dict[str, Any]:
    # Example changes:
    # - consolidate loop clamp values; rename log level values; etc.
    if "dacMin" not in doc:
        doc["dacMin"] = 0
    if "dacMax" not in doc:
        doc["dacMax"] = 65535

    # Normalize logLevel capitalization
    if "logLevel" in doc:
        doc["logLevel"] = str(doc["logLevel"]).upper()

    doc["schemaVersion"] = 3
    return doc

MIGRATORS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {
    1: migrateV1ToV2,
    2: migrateV2ToV3,
}

def applyMigrations(doc: dict[str, Any]) -> dict[str, Any]:
    version = int(doc.get("schemaVersion", 1))
    while version < CURRENT_SCHEMA_VERSION:
        if version not in MIGRATORS:
            raise RuntimeError(f"no migrator for version {version}")
        doc = MIGRATORS[version](doc)
        version = int(doc.get("schemaVersion", version))
    return doc

# --------- load / save ---------
def loadConfig(path: str) -> Config:
    y = yamlLoader()
    if not os.path.exists(path):
        # start with defaults; write an initial file
        cfg = Config()
        saveConfig(path, cfg, makeBackup=False)
        return cfg

    with open(path, encoding="utf-8") as f:
        doc = y.load(f) or {}

    # migrate forward
    doc = applyMigrations(doc)

    # validate and coerce into our model
    try:
        cfg = Config.model_validate(doc)
    except ValidationError as e:
        raise RuntimeError(f"config validation failed: {e}") from e

    # write back canonical latest schema (round-trip tries to preserve comments)
    saveConfig(path, cfg, makeBackup=True)
    return cfg

def saveConfig(path: str, cfg: Config, makeBackup: bool = True) -> None:
    y = yamlLoader()
    # Load existing (if present) to preserve comments; else start fresh
    baseDoc = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                baseDoc = y.load(f) or {}
        except Exception:
            baseDoc = {}

    newDoc = baseDoc
    for k in list(newDoc.keys()):
        if k not in cfg.model_dump().keys():
            del newDoc[k]
    for k, v in cfg.model_dump().items():
        newDoc[k] = v

    tmpDir = os.path.dirname(path) or "."
    fd, tmpPath = tempfile.mkstemp(prefix=".cfg-", dir=tmpDir)
    os.close(fd)
    try:
        with open(tmpPath, "w", encoding="utf-8") as f:
            y.dump(newDoc, f)

        if makeBackup and os.path.exists(path):
            shutil.copy2(path, path + ".bak")

        # Optional lock
        if FileLock is not None:
            with FileLock(path + ".lock"):
                os.replace(tmpPath, path)
        else:
            os.replace(tmpPath, path)
    finally:
        if os.path.exists(tmpPath):
            try:
                os.remove(tmpPath)
            except Exception:
                pass
