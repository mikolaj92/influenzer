"""Credential isolation and safe outbound HTTPS helpers.

Credential references are identifiers only. Secret values are resolved at the
process boundary and are never part of a manifest or command argument.
"""
from __future__ import annotations

import contextlib
import http.client
import ipaddress
import os
import re
import shutil
import socket
import ssl
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterator, Mapping, Sequence
from urllib.parse import urljoin, urlsplit


class SecurityError(ValueError):
    """Base error for a rejected security boundary input."""


class CredentialError(SecurityError):
    """A credential reference could not be parsed or resolved."""


class FetchError(SecurityError):
    """A URL or response failed the outbound-fetch policy."""


class WorkspacePermissionError(SecurityError):
    """Workspace file or directory is looser than 0600/0700."""


PRIVATE_FILE_MODE = 0o600
PRIVATE_DIR_MODE = 0o700


_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SERVICE_PART = re.compile(r"^[^/\\\x00\r\n]+$")
_SAFE_CHILD_ENV = frozenset({"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "TZ"})
_METADATA_IPS = frozenset({"169.254.169.254", "100.100.100.200", "fd00:ec2::254"})


def parse_credential_ref(ref: str) -> tuple[str, str, str | None]:
    """Parse only ``env:NAME`` and ``keychain:SERVICE/ACCOUNT`` references."""
    if not isinstance(ref, str):
        raise CredentialError("credential reference must be a string")
    if ref.startswith("env:"):
        name = ref[4:]
        if not _ENV_NAME.fullmatch(name):
            raise CredentialError("invalid environment credential reference")
        return "env", name, None
    if ref.startswith("keychain:"):
        parts = ref[9:].split("/")
        if len(parts) != 2 or not all(_SERVICE_PART.fullmatch(part) for part in parts):
            raise CredentialError("invalid keychain credential reference")
        return "keychain", parts[0], parts[1]
    raise CredentialError("credential reference must be env:NAME or keychain:SERVICE/ACCOUNT")


class CredentialProvider:
    """Provider interface used by subprocess boundaries."""

    def resolve(self, ref: str) -> str:
        raise NotImplementedError


class EnvCredentialProvider(CredentialProvider):
    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self.environ = os.environ if environ is None else environ

    def resolve(self, ref: str) -> str:
        kind, name, _ = parse_credential_ref(ref)
        if kind != "env":
            raise CredentialError("environment provider received a non-env reference")
        value = self.environ.get(name)
        if value is None or value == "":
            raise CredentialError(f"credential environment variable is unavailable: {name}")
        return value


class KeychainCredentialProvider(CredentialProvider):
    """Resolve one macOS generic-password item without exposing it in argv."""

    def __init__(self, *, executable: str = "security", timeout: float = 5.0) -> None:
        self.executable = executable
        self.timeout = timeout

    def resolve(self, ref: str) -> str:
        kind, service, account = parse_credential_ref(ref)
        if kind != "keychain" or account is None:
            raise CredentialError("keychain provider received a non-keychain reference")
        try:
            completed = subprocess.run(
                [self.executable, "find-generic-password", "-s", service, "-a", account, "-w"],
                check=False,
                capture_output=True,
                timeout=self.timeout,
                text=True,
                env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CredentialError("keychain lookup failed") from exc
        if completed.returncode != 0 or not completed.stdout.strip():
            raise CredentialError("keychain item unavailable")
        return completed.stdout.rstrip("\r\n")


def resolve_credential(ref: str, *, environ: Mapping[str, str] | None = None,
                       keychain: CredentialProvider | None = None) -> str:
    kind, _, _ = parse_credential_ref(ref)
    if kind == "env":
        return EnvCredentialProvider(environ).resolve(ref)
    return (keychain or KeychainCredentialProvider()).resolve(ref)


def build_child_env(
    credential_refs: Sequence[str] = (),
    *,
    environ: Mapping[str, str] | None = None,
    providers: Mapping[str, CredentialProvider] | None = None,
    base: Mapping[str, str] | None = None,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build a minimal child environment, resolving refs only into child slots."""
    source = os.environ if environ is None else environ
    safe = {key: value for key, value in source.items() if key in _SAFE_CHILD_ENV}
    if base:
        safe.update({key: value for key, value in base.items() if key in _SAFE_CHILD_ENV})
    if extra:
        for key, value in extra.items():
            if not _ENV_NAME.fullmatch(key):
                raise SecurityError("invalid child environment variable")
            safe[key] = str(value)
    providers = providers or {}
    used: set[str] = set()
    for index, ref in enumerate(credential_refs):
        kind, name, _ = parse_credential_ref(ref)
        slot = name if kind == "env" else f"INFLUENZER_CREDENTIAL_{index}"
        if slot in used:
            raise CredentialError("duplicate credential environment slot")
        used.add(slot)
        provider = providers.get(kind)
        value = provider.resolve(ref) if provider is not None else resolve_credential(ref, environ=source)
        safe[slot] = value
    return safe


child_environment = build_child_env


def manifest_for_child(manifest: Mapping[str, Any], credential_refs: Sequence[str] = ()) -> dict[str, Any]:
    """Copy a manifest while retaining only credential reference names."""
    out = _copy_without_secret_keys(manifest)
    refs = []
    for ref in credential_refs:
        parse_credential_ref(ref)
        refs.append(ref)
    if refs:
        out["credential_refs"] = refs
    return out


def _copy_without_secret_keys(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _copy_without_secret_keys(item)
            for key, item in value.items()
            if str(key).lower() not in {"secret", "token", "password", "credential", "credential_value"}
        }
    if isinstance(value, list):
        return [_copy_without_secret_keys(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_copy_without_secret_keys(item) for item in value)
    return value


def redact(value: str, secrets: Sequence[str] = ()) -> str:
    output = str(value)
    for secret in secrets:
        if secret:
            output = output.replace(secret, "[REDACTED]")
    return output


def path_mode(path: Path) -> int:
    return stat.S_IMODE(Path(path).stat().st_mode)


def _has_group_or_other(path: Path) -> bool:
    return bool(path_mode(path) & 0o077)


def require_private_file(path: Path) -> None:
    """Fail closed when a file is looser than 0600."""
    target = Path(path)
    if not target.is_file() or _has_group_or_other(target):
        raise WorkspacePermissionError("workspace file must be 0600")


def require_private_dir(path: Path) -> None:
    """Fail closed when a directory is looser than 0700."""
    target = Path(path)
    if not target.is_dir() or _has_group_or_other(target):
        raise WorkspacePermissionError("workspace directory must be 0700")


def ensure_private_dir(path: Path) -> Path:
    """Create ``path`` as 0700. Existing looser directories refuse to start."""
    target = Path(path)
    if not target.exists():
        if target.parent != target:
            ensure_private_dir(target.parent)
        try:
            os.mkdir(target, PRIVATE_DIR_MODE)
        except FileExistsError:
            pass
    require_private_dir(target)
    return target


def create_private_file(path: Path) -> Path:
    """Create an empty 0600 file when missing. Existing files are left to the caller."""
    target = Path(path)
    if target.exists():
        return target
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, PRIVATE_FILE_MODE)
    except FileExistsError:
        return target
    os.close(fd)
    return target


def write_private_text(path: Path, text: str) -> None:
    """Write UTF-8 as 0600. An existing looser file is silence, not a rewrite."""
    target = Path(path)
    ensure_private_dir(target.parent)
    encoded = text.encode("utf-8")
    if target.exists():
        require_private_file(target)
        target.write_bytes(encoded)
        require_private_file(target)
        return
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, PRIVATE_FILE_MODE)
    try:
        os.write(fd, encoded)
    finally:
        os.close(fd)
    require_private_file(target)


def require_workspace_permissions(home: Path, *, config_file: Path | None = None, state_db: Path | None = None) -> None:
    """Refuse to start when home, config, or state.db are world/group readable."""
    require_private_dir(home)
    if config_file is not None and Path(config_file).exists():
        require_private_file(config_file)
        require_private_dir(Path(config_file).parent)
    if state_db is not None and Path(state_db).exists():
        require_private_file(state_db)


@contextlib.contextmanager
def isolated_home() -> Iterator[Path]:
    """Yield a mode-0700 temporary HOME and remove it on every exit path."""
    path = Path(tempfile.mkdtemp(prefix="influenzer-home-"))
    path.chmod(PRIVATE_DIR_MODE)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _normal_host(host: str) -> str:
    host = host.strip().rstrip(".").lower()
    if not host:
        raise FetchError("URL host is required")
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise FetchError("invalid URL host") from exc


def _account_host(host: str) -> str:
    parsed = urlsplit(host if "://" in host else f"https://{host}")
    if parsed.username or parsed.password or not parsed.hostname:
        raise FetchError("invalid account host binding")
    return _normal_host(parsed.hostname)


def _is_forbidden_ip(address: str) -> bool:
    raw = address.split("%", 1)[0]
    if raw in _METADATA_IPS:
        return True
    try:
        parsed = ipaddress.ip_address(raw)
    except ValueError:
        return True
    return parsed.is_private or parsed.is_loopback or parsed.is_link_local or parsed.is_unspecified or parsed.is_multicast or parsed.is_reserved


def resolve_public_addresses(host: str, port: int = 443) -> tuple[str, ...]:
    """Resolve and reject every unsafe result, failing closed on DNS errors."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise FetchError("unable to resolve fetch host") from exc
    addresses = tuple(dict.fromkeys(str(info[4][0]) for info in infos))
    if not addresses or any(_is_forbidden_ip(address) for address in addresses):
        raise FetchError("fetch target resolves to a private or special-use address")
    return addresses


def validate_fetch_url(url: str, *, account_host: str | None = None,
                       allowed_schemes: Sequence[str] = ("https",),
                       resolve: bool = True) -> tuple[Any, str]:
    """Validate HTTPS, host binding, and target address before a fetch."""
    parsed = urlsplit(url)
    schemes = {scheme.lower() for scheme in allowed_schemes}
    if parsed.scheme.lower() not in schemes or parsed.scheme.lower() != "https":
        raise FetchError("outbound fetch requires HTTPS")
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise FetchError("userinfo and fragments are not allowed in fetch URLs")
    if not parsed.hostname:
        raise FetchError("URL host is required")
    host = _normal_host(parsed.hostname)
    if account_host is not None and host != _account_host(account_host):
        raise FetchError("URL host does not match account host binding")
    try:
        port = parsed.port or 443
    except ValueError as exc:
        raise FetchError("invalid URL port") from exc
    if not (1 <= port <= 65535):
        raise FetchError("invalid URL port")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if _is_forbidden_ip(host):
            raise FetchError("private or special-use fetch target denied")
    if resolve:
        resolve_public_addresses(host, port)
    return parsed, host


def validate_redirect_url(current_url: str, location: str, *, account_host: str | None = None,
                          resolve: bool = True) -> str:
    """Resolve and validate one redirect target before following it."""
    if not isinstance(location, str) or not location.strip():
        raise FetchError("redirect location is missing")
    target = urljoin(current_url, location)
    validate_fetch_url(target, account_host=account_host, resolve=resolve)
    return target


def validate_content_length(length: str | None, *, max_bytes: int) -> None:
    if max_bytes <= 0:
        raise FetchError("invalid content size limit")
    if length is None:
        return
    try:
        value = int(length)
    except (TypeError, ValueError) as exc:
        raise FetchError("invalid response content length") from exc
    if value < 0 or value > max_bytes:
        raise FetchError("response body exceeds size limit")


def validate_content_type(content_type: str | None, *, allowed: Sequence[str]) -> str:
    value = (content_type or "").split(";", 1)[0].strip().lower()
    if not value or not any(value == item.lower() or item.endswith("/") and value.startswith(item.lower()) for item in allowed):
        raise FetchError("response content type is not allowed")
    return value


@dataclass(frozen=True)
class FetchResponse:
    url: str
    status: int
    headers: Mapping[str, str]
    body: bytes


class _BoundHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection pinned to addresses resolved by validation."""

    def __init__(self, host: str, port: int, addresses: Sequence[str], timeout: float) -> None:
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self._addresses = tuple(addresses)

    def connect(self) -> None:
        last: OSError | None = None
        for address in self._addresses:
            sock: socket.socket | None = None
            try:
                family = socket.AF_INET6 if ":" in address else socket.AF_INET
                sock = socket.socket(family, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                target = (address, self.port, 0, 0) if family == socket.AF_INET6 else (address, self.port)
                sock.connect(target)
                self.sock = self._context.wrap_socket(sock, server_hostname=self._tunnel_host or self.host)
                return
            except OSError as exc:
                last = exc
                if sock is not None:
                    with contextlib.suppress(OSError):
                        sock.close()
        raise FetchError("unable to connect to validated fetch target") from last


def fetch_url(
    url: str,
    *,
    account_host: str | None = None,
    max_bytes: int = 10 * 1024 * 1024,
    allowed_content_types: Sequence[str] = ("image/", "text/plain", "application/json"),
    timeout: float = 10.0,
    max_redirects: int = 3,
) -> FetchResponse:
    """Fetch bounded content with redirect and host/address revalidation."""
    if max_bytes <= 0 or timeout <= 0 or max_redirects < 0:
        raise FetchError("invalid fetch bounds")
    current = url
    for redirect_count in range(max_redirects + 1):
        parsed, host = validate_fetch_url(current, account_host=account_host)
        port = parsed.port or 443
        addresses = resolve_public_addresses(host, port)
        connection = _BoundHTTPSConnection(host, port, addresses, timeout)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        try:
            connection.request("GET", path, headers={"Host": parsed.hostname or host, "Accept": ", ".join(allowed_content_types)})
            response = connection.getresponse()
            location = response.getheader("Location")
            if response.status in {301, 302, 303, 307, 308} and location:
                if redirect_count >= max_redirects:
                    raise FetchError("redirect limit exceeded")
                current = validate_redirect_url(current, location, account_host=account_host)
                continue
            content_type = validate_content_type(response.getheader("Content-Type"), allowed=allowed_content_types)
            validate_content_length(response.getheader("Content-Length"), max_bytes=max_bytes)
            body = bytearray()
            while True:
                chunk = response.read(min(64 * 1024, max_bytes - len(body) + 1))
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > max_bytes:
                    raise FetchError("response body exceeds size limit")
            return FetchResponse(current, response.status, MappingProxyType({k: v for k, v in response.getheaders()}), bytes(body))
        except FetchError:
            raise
        except (OSError, socket.timeout, ssl.SSLError) as exc:
            raise FetchError("HTTPS fetch failed") from exc
        finally:
            connection.close()
    raise FetchError("redirect limit exceeded")


safe_fetch = fetch_url
validate_url = validate_fetch_url

__all__ = [
    "CredentialError", "CredentialProvider", "EnvCredentialProvider", "FetchError",
    "FetchResponse", "KeychainCredentialProvider", "PRIVATE_DIR_MODE", "PRIVATE_FILE_MODE",
    "SecurityError", "WorkspacePermissionError", "build_child_env", "child_environment",
    "create_private_file", "ensure_private_dir", "fetch_url", "isolated_home",
    "manifest_for_child", "parse_credential_ref", "path_mode", "redact",
    "require_private_dir", "require_private_file", "require_workspace_permissions",
    "resolve_credential", "resolve_public_addresses", "safe_fetch", "validate_content_length",
    "validate_content_type", "validate_fetch_url", "validate_redirect_url", "validate_url",
    "write_private_text",
]
