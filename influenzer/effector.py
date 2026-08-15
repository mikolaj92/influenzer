"""Strict handler runner and result boundary for Influenzer."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from . import envelope
from .catalog import resolve
from .hom import HomError, apply_brief, brief_from_mapping, decision_to_dict

_SECRET_KEY = re.compile(
    r"(?:token|password|passwd|secret|api[_-]?key|authorization|credential|access[_-]?token|refresh[_-]?token|client[_-]?secret)",
    re.IGNORECASE,
)
_SECRET_REF = re.compile(r"^(?:env|keychain):[^\s]+$", re.IGNORECASE)
_SECRET_TEXT = re.compile(
    r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?|(?:token|password|secret|api[_-]?key)\s*[:=]\s*)[^\s,;]+"
)


def noop(request: Mapping[str, Any]) -> dict[str, Any]:
    """Reference handler useful for path wiring and dry-run checks."""

    return envelope.noop("no operation")


def echo(request: Mapping[str, Any]) -> dict[str, Any]:
    """Reference non-mutating handler; output is redacted by :func:`run`."""

    return envelope.ok(status="echo", echo=dict(request))


# Look/pass/angle stay on this dry-run catalog. Live is grant+intent on the
# scheduler path, not a flag that flips these names into publishers.
_LOOK_PASS_ANGLE = frozenset(
    {"score_brief", "look", "pass", "angle", "hom_pass", "hom_outbox"}
)


def score_brief(request: Mapping[str, Any]) -> dict[str, Any]:
    """Pure HoM score. Drafts are decisions, not live publishes."""

    payload = envelope.input_of(request)
    if not payload:
        cfg = envelope.cfg_of(request)
        payload = dict(cfg.get("brief") or request.get("brief") or {})
    try:
        brief = brief_from_mapping(payload)
        decision = apply_brief(brief)
    except (HomError, ValueError, TypeError, KeyError) as exc:
        return envelope.fail(str(exc), failure_class="validation")
    out = decision_to_dict(decision)
    return envelope.result(status="ok", ok=True, mutated=False, **out)


def _handler_name(request: Mapping[str, Any]) -> str | None:
    name = request.get("handler")
    if name is None:
        name = request.get("name")
    config = request.get("config")
    if name is None and isinstance(config, Mapping):
        name = config.get("handler")
    return name if isinstance(name, str) else None


def _dry_run(request: Mapping[str, Any]) -> bool:
    """Read dry-run with authored input taking precedence over config.

    Look/pass/angle cannot leave dry-run. ``live_enabled`` is not an override.
    Live stays a separate grant+intent on the scheduler path.
    """

    if _handler_name(request) in _LOOK_PASS_ANGLE:
        return True
    input_data = request.get("input")
    if isinstance(input_data, Mapping) and "dry_run" in input_data:
        value = input_data["dry_run"]
    else:
        config = request.get("config")
        if isinstance(config, Mapping) and "dry_run" in config:
            value = config["dry_run"]
        else:
            value = request.get("dry_run", True)
    if type(value) is not bool:
        raise TypeError("dry_run must be a boolean")
    return value


def _secret_values(value: Any, *, key: str = "") -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            found.update(_secret_values(child_value, key=str(child_key)))
    elif isinstance(value, list):
        for child in value:
            found.update(_secret_values(child, key=key))
    elif isinstance(value, str) and _SECRET_KEY.search(key) and value:
        found.add(value)
    return found


def redact(value: Any, *, _secrets: set[str] | None = None, key: str = "") -> Any:
    """Return JSON-safe output with credentials and credential references removed."""

    secrets = _secrets if _secrets is not None else _secret_values(value)
    if _SECRET_KEY.search(key):
        return "<redacted>"
    if isinstance(value, Mapping):
        return {str(child_key): redact(child_value, _secrets=secrets, key=str(child_key)) for child_key, child_value in value.items()}
    if isinstance(value, list):
        return [redact(child, _secrets=secrets, key=key) for child in value]
    if isinstance(value, str):
        if value in secrets or _SECRET_REF.fullmatch(value):
            return "<redacted>"
        redacted = value
        for secret in secrets:
            redacted = redacted.replace(secret, "<redacted>")
        return _SECRET_TEXT.sub(r"\1<redacted>", redacted)
    return value


def normalize_result(raw: Any, request: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a handler envelope and enforce the request's dry-run mode."""

    if not isinstance(raw, Mapping):
        raise TypeError("handler result must be a JSON object")
    payload = dict(raw)
    if not isinstance(payload.get("status"), str) or not payload["status"]:
        raise TypeError("handler result status must be a non-empty string")
    if type(payload.get("ok")) is not bool:
        raise TypeError("handler result ok must be a boolean")
    if type(payload.get("mutated")) is not bool:
        raise TypeError("handler result mutated must be a boolean")
    expected = _dry_run(request)
    if "dry_run" in payload and type(payload["dry_run"]) is not bool:
        raise TypeError("result dry_run must be a boolean")
    if "dry_run" in payload and payload["dry_run"] is not expected:
        raise ValueError("result dry_run conflicts with request")
    if expected and payload["mutated"]:
        raise ValueError("dry-run handler reported mutation")
    payload["dry_run"] = expected
    return payload


def run(request: Mapping[str, Any]) -> dict[str, Any]:
    """Dispatch one allowlisted handler and always return a safe envelope."""

    if not isinstance(request, Mapping):
        return envelope.fail("invalid_request")
    secrets = _secret_values(request)
    try:
        handler = resolve(_handler_name(request))
        raw = handler(dict(request))
        result = normalize_result(raw, request)
    except Exception as exc:
        result = envelope.fail("effector_boundary_failed", error=str(exc))
    return redact(result, _secrets=secrets)


__all__ = ["echo", "noop", "normalize_result", "redact", "run", "score_brief"]


if __name__ == "__main__":  # pragma: no cover
    import json
    import sys

    print(json.dumps(run(json.load(sys.stdin)), sort_keys=True))
