"""Small local workspace configuration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    pass


ENV_CONFIG = "HERMES_INFLUENZER_CONFIG"
DEFAULT_HOME = Path.home() / ".hermes" / "influenzer"


@dataclass(frozen=True)
class Config:
    home: Path
    scheduler_live_enabled: bool = False

    @property
    def state_db(self) -> Path:
        return self.home / "state.db"

    @property
    def runtime_db(self) -> Path:
        return self.home / "runtime.db"

    @property
    def artifacts(self) -> Path:
        return self.home / "artifacts" / "sha256"


def config_path(explicit: str | None = None) -> Path:
    return Path(explicit or os.environ.get(ENV_CONFIG, DEFAULT_HOME / "config.json")).expanduser()


def load_config(explicit: str | None = None) -> Config:
    path = config_path(explicit)
    if not path.exists():
        return Config(home=path.parent)
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError("config must be a JSON object")
    home = Path(str(data.get("home") or path.parent)).expanduser()
    scheduler = data.get("scheduler") or {}
    if not isinstance(scheduler, dict) or type(scheduler.get("live_enabled", False)) is not bool:
        raise ConfigError("scheduler.live_enabled must be boolean")
    return Config(home=home, scheduler_live_enabled=bool(scheduler.get("live_enabled", False)))


def write_config(path: Path, config: Config) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "home": str(config.home),
                "scheduler": {"live_enabled": config.scheduler_live_enabled},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
