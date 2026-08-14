"""Small local workspace configuration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    pass


class WorkspacePermissionError(ConfigError):
    """Home, config, or state.db is looser than owner-only. Fail closed."""


ENV_CONFIG = "HERMES_INFLUENZER_CONFIG"
DEFAULT_HOME = Path.home() / ".hermes" / "influenzer"
DIR_MODE = 0o700
FILE_MODE = 0o600
PERMISSION_REFUSED = {
    "status": "silence",
    "reason": "workspace_permissions",
    "published": False,
}
_SIDECARS = ("-wal", "-shm", "-journal")


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


def _mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


def _too_open(path: Path, allowed: int) -> bool:
    return _mode(path) & ~allowed != 0


def _secure_mkdir(path: Path) -> None:
    if path.exists():
        if not path.is_dir() or _too_open(path, DIR_MODE):
            raise WorkspacePermissionError("workspace directory must be 0700")
        return
    path.mkdir(mode=DIR_MODE, parents=False, exist_ok=False)
    path.chmod(DIR_MODE)


def ensure_private_dir(path: Path) -> None:
    """Create ``path`` as 0700, or refuse an existing looser directory."""
    path = Path(path)
    if not path.exists():
        missing: list[Path] = []
        cursor = path
        while not cursor.exists():
            missing.append(cursor)
            if cursor.parent == cursor:
                break
            cursor = cursor.parent
        for item in reversed(missing):
            _secure_mkdir(item)
        return
    _secure_mkdir(path)


def mkdir_private(path: Path) -> None:
    """Create missing directories as 0700. Existing directories are left as-is."""
    path = Path(path)
    if path.exists():
        if not path.is_dir():
            raise WorkspacePermissionError("workspace directory must be 0700")
        return
    ensure_private_dir(path)


def ensure_private_file(path: Path) -> None:
    """Create or keep ``path`` at 0600. A looser existing file is silence."""
    path = Path(path)
    if path.exists():
        if not path.is_file() or _too_open(path, FILE_MODE):
            raise WorkspacePermissionError("workspace file must be 0600")
        path.chmod(FILE_MODE)
        return
    if not path.parent.exists():
        ensure_private_dir(path.parent)
    path.touch(mode=FILE_MODE, exist_ok=False)
    path.chmod(FILE_MODE)


def require_private_dir(path: Path) -> None:
    if not path.is_dir() or _too_open(path, DIR_MODE):
        raise WorkspacePermissionError("workspace directory must be 0700")


def require_private_file(path: Path) -> None:
    if not path.is_file() or _too_open(path, FILE_MODE):
        raise WorkspacePermissionError("workspace file must be 0600")


def state_sidecars(db_path: Path) -> tuple[Path, ...]:
    return tuple(Path(str(db_path) + suffix) for suffix in _SIDECARS)


def require_private_state(db_path: Path) -> None:
    if db_path.exists():
        require_private_file(db_path)
    for sidecar in state_sidecars(db_path):
        if sidecar.exists():
            require_private_file(sidecar)


def tighten_private_state(db_path: Path) -> None:
    if db_path.exists():
        os.chmod(db_path, FILE_MODE)
    for sidecar in state_sidecars(db_path):
        if sidecar.exists():
            os.chmod(sidecar, FILE_MODE)


def require_workspace_permissions(home: Path, *, config: Path | None = None, state_db: Path | None = None) -> None:
    """Fail closed when home, config, or state.db is world/group readable."""
    require_private_dir(home)
    if config is not None and config.exists():
        require_private_file(config)
    require_private_state(home / "state.db" if state_db is None else state_db)


def prepare_home(config: Config) -> None:
    """Create the workspace tree as 0700, or refuse a looser existing home."""
    ensure_private_dir(config.home)
    mkdir_private(config.artifacts)


def open_workspace(explicit: str | None = None) -> Config:
    """Load config, create a private home, or refuse a looser existing tree."""
    path = config_path(explicit)
    if path.exists():
        require_private_file(path)
    cfg = load_config(explicit)
    if cfg.home.exists():
        require_workspace_permissions(cfg.home, config=path if path.exists() else None, state_db=cfg.state_db)
        mkdir_private(cfg.artifacts)
    else:
        prepare_home(cfg)
    return cfg


def permission_exit() -> int:
    print(json.dumps(PERMISSION_REFUSED, sort_keys=True))
    return 2


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
    path = Path(path)
    if not path.parent.exists():
        ensure_private_dir(path.parent)
    elif path.parent == Path(config.home):
        require_private_dir(path.parent)
    if path.exists():
        require_private_file(path)
    else:
        ensure_private_file(path)
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
    path.chmod(FILE_MODE)
    if config.home.exists():
        require_workspace_permissions(config.home, config=path, state_db=config.state_db)
