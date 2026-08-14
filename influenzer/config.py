"""Small local workspace configuration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from influenzer.security import (
    WorkspacePermissionError,
    chmod_private_file,
    mkdir_private,
    require_private_file,
    require_workspace,
)


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


def ensure_home(home: Path) -> Path:
    """Create the workspace catalog as 0700, or refuse a looser existing tree."""
    mkdir_private(home, parents=True)
    mkdir_private(home / "artifacts", parents=True)
    mkdir_private(home / "artifacts" / "sha256", parents=True)
    return home


def _check_workspace(home: Path, *, config_file: Path | None = None) -> None:
    require_workspace(home, config_path=config_file, state_db=home / "state.db")
    for sidecar in (home / "state.db-wal", home / "state.db-shm"):
        if sidecar.exists():
            require_private_file(sidecar)


def load_config(explicit: str | None = None) -> Config:
    path = config_path(explicit)
    if not path.exists():
        _check_workspace(path.parent)
        return Config(home=path.parent)
    require_private_file(path)
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError("config must be a JSON object")
    home = Path(str(data.get("home") or path.parent)).expanduser()
    scheduler = data.get("scheduler") or {}
    if not isinstance(scheduler, dict) or type(scheduler.get("live_enabled", False)) is not bool:
        raise ConfigError("scheduler.live_enabled must be boolean")
    _check_workspace(home, config_file=path)
    return Config(home=home, scheduler_live_enabled=bool(scheduler.get("live_enabled", False)))


def write_config(path: Path, config: Config) -> None:
    if path.exists():
        require_private_file(path)
    mkdir_private(path.parent, parents=True)
    mkdir_private(config.home, parents=True)
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
    chmod_private_file(path)


__all__ = [
    "Config",
    "ConfigError",
    "DEFAULT_HOME",
    "ENV_CONFIG",
    "WorkspacePermissionError",
    "config_path",
    "ensure_home",
    "load_config",
    "write_config",
]
