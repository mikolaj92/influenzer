from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    pass


DEFAULT_CONFIG_PATH = Path.home() / ".hermes" / "build-in-public" / "config.yaml"
ENV_CONFIG = "HERMES_BUILD_IN_PUBLIC_CONFIG"
SOCIAL_KEY_PARTS = (
    ("x", "api", "key"),
    ("twitter", "token"),
    ("mastodon", "token"),
    ("reddit", "client", "secret"),
)


@dataclass(frozen=True)
class SourceConfig:
    enabled: bool = False
    repos: tuple[str, ...] = ()
    path: str | None = None

    @classmethod
    def from_mapping(cls, value: Any) -> "SourceConfig":
        if value is None:
            return cls()
        if not isinstance(value, dict):
            raise ConfigError("source config must be an object")
        repos = value.get("repos", [])
        if repos is None:
            repos = []
        if not isinstance(repos, list) or not all(isinstance(item, str) for item in repos):
            raise ConfigError("source repos must be a list of strings")
        path = value.get("path")
        if path is not None and not isinstance(path, str):
            raise ConfigError("source path must be a string")
        return cls(enabled=bool(value.get("enabled", False)), repos=tuple(repos), path=path)


@dataclass(frozen=True)
class Sources:
    github: SourceConfig = field(default_factory=SourceConfig)
    kanban: SourceConfig = field(default_factory=SourceConfig)
    manual: SourceConfig = field(default_factory=SourceConfig)

    @classmethod
    def from_mapping(cls, value: Any) -> "Sources":
        if value is None:
            value = {}
        if not isinstance(value, dict):
            raise ConfigError("sources must be an object")
        return cls(
            github=SourceConfig.from_mapping(value.get("github")),
            kanban=SourceConfig.from_mapping(value.get("kanban")),
            manual=SourceConfig.from_mapping(value.get("manual")),
        )


@dataclass(frozen=True)
class BuildInPublicConfig:
    version: int = 1
    output_mode: str = "draft-only"
    output_dir: str = "./build-in-public-output"
    maintainer: str = "maintainer"
    audience: str = "builders and maintainers"
    sources: Sources = field(default_factory=Sources)
    redaction_enabled: bool = True
    publish: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "BuildInPublicConfig":
        if not isinstance(data, dict):
            raise ConfigError("config must be an object")
        reject_social_keys(data)
        output_mode = str(data.get("output_mode", "draft-only"))
        if output_mode != "draft-only":
            raise ConfigError("only draft-only output_mode is supported in v0")
        publish = data.get("publish", {}) or {}
        if not isinstance(publish, dict):
            raise ConfigError("publish must be an object")
        if bool(publish.get("enabled", False)):
            raise ConfigError("publishing is not supported in v0")
        return cls(
            version=int(data.get("version", 1)),
            output_mode=output_mode,
            output_dir=str(data.get("output_dir", "./build-in-public-output")),
            maintainer=str(data.get("maintainer", "maintainer")),
            audience=str(data.get("audience", "builders and maintainers")),
            sources=Sources.from_mapping(data.get("sources")),
            redaction_enabled=bool((data.get("redaction") or {}).get("enabled", True)) if isinstance(data.get("redaction", {}), dict) else True,
            publish=publish,
        )

    def output_path(self) -> Path:
        return Path(self.output_dir).expanduser()

    def should_write(self, live_flag: bool) -> bool:
        return bool(live_flag) and self.output_mode == "draft-only"


def reject_social_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            for parts in SOCIAL_KEY_PARTS:
                if normalized == "_".join(parts):
                    raise ConfigError("social publishing credentials are not accepted")
            reject_social_keys(child)
    elif isinstance(value, list):
        for child in value:
            reject_social_keys(child)


def _parse_scalar(value: str) -> Any:
    text = value.strip()
    if text == "":
        return ""
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none", "~"}:
        return None
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    return text


def _parse_yaml_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    current_indent, content = lines[index]
    if current_indent < indent:
        return {}, index
    if content.startswith("- "):
        return _parse_yaml_list(lines, index, indent)
    return _parse_yaml_map(lines, index, indent)


def _parse_yaml_map(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[dict[str, Any], int]:
    data: dict[str, Any] = {}
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ConfigError(f"unexpected indentation near: {content}")
        if content.startswith("- "):
            break
        if ":" not in content:
            raise ConfigError(f"invalid YAML line: {content}")
        key, raw_value = content.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if not key:
            raise ConfigError("empty YAML key")
        index += 1
        if raw_value:
            data[key] = _parse_scalar(raw_value)
        else:
            value, index = _parse_yaml_block(lines, index, indent + 2)
            data[key] = value
    return data, index


def _parse_yaml_list(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent != indent or not content.startswith("- "):
            break
        item = content[2:].strip()
        index += 1
        if item == "":
            value, index = _parse_yaml_block(lines, index, indent + 2)
            items.append(value)
        elif ":" in item:
            key, raw_value = item.split(":", 1)
            entry: dict[str, Any] = {}
            key = key.strip()
            raw_value = raw_value.strip()
            if raw_value:
                entry[key] = _parse_scalar(raw_value)
            else:
                value, index = _parse_yaml_block(lines, index, indent + 2)
                entry[key] = value
            if index < len(lines) and lines[index][0] == indent + 2 and not lines[index][1].startswith("- "):
                extra, index = _parse_yaml_map(lines, index, indent + 2)
                entry.update(extra)
            items.append(entry)
        else:
            items.append(_parse_scalar(item))
    return items, index


def _load_simple_yaml(text: str) -> dict[str, Any]:
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2 != 0:
            raise ConfigError(f"YAML indentation must use two spaces: {raw}")
        lines.append((indent, stripped))
    if not lines:
        return {}
    data, index = _parse_yaml_block(lines, 0, lines[0][0])
    if index != len(lines):
        raise ConfigError("could not parse complete YAML document")
    if not isinstance(data, dict):
        raise ConfigError("config file must contain an object")
    return data


def load_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml
    except Exception:
        loaded = _load_simple_yaml(text)
    else:
        loaded = yaml.safe_load(text) or {}
    if not isinstance(loaded, dict):
        raise ConfigError("config file must contain an object")
    return loaded


def resolve_config_path(path: str | Path | None = None) -> Path:
    if path:
        return Path(path).expanduser()
    env = os.environ.get(ENV_CONFIG)
    if env:
        return Path(env).expanduser()
    return DEFAULT_CONFIG_PATH


def load_config(path: str | Path | None = None) -> BuildInPublicConfig:
    resolved = resolve_config_path(path)
    if not resolved.exists():
        raise ConfigError(f"config file does not exist: {resolved}")
    return BuildInPublicConfig.from_mapping(load_mapping(resolved))
