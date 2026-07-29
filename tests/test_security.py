from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from influenzer.security import (
    CredentialError,
    EnvCredentialProvider,
    FetchError,
    build_child_env,
    fetch_url,
    isolated_home,
    manifest_for_child,
    parse_credential_ref,
    validate_fetch_url,
)


class CredentialSecurityTests(unittest.TestCase):
    def test_env_provider_and_child_environment_isolate_sentinel(self) -> None:
        sentinel = "credential-sentinel-not-in-manifest"
        env = {"SOCIAL_TOKEN": sentinel, "UNSAFE_PARENT": "do-not-inherit", "PATH": "/bin"}
        child = build_child_env(("env:SOCIAL_TOKEN",), environ=env)
        self.assertEqual(child["SOCIAL_TOKEN"], sentinel)
        self.assertNotIn("UNSAFE_PARENT", child)
        manifest = manifest_for_child({"credential_refs": ["env:SOCIAL_TOKEN"], "payload": {"text": "hello"}}, ("env:SOCIAL_TOKEN",))
        self.assertNotIn(sentinel, repr(manifest))
        self.assertEqual(EnvCredentialProvider(env).resolve("env:SOCIAL_TOKEN"), sentinel)

    def test_plaintext_and_malformed_refs_rejected(self) -> None:
        for ref in ("plaintext-secret", "file:/tmp/token", "env:", "env:bad-name", "keychain:only-service", "keychain:s/a/b"):
            with self.subTest(ref=ref), self.assertRaises(CredentialError):
                parse_credential_ref(ref)
        self.assertEqual(parse_credential_ref("keychain:service/account"), ("keychain", "service", "account"))

    def test_isolated_home_removed_on_exit(self) -> None:
        with isolated_home() as home:
            path = home
            self.assertEqual(home.stat().st_mode & 0o777, 0o700)
            (home / "state").write_text("not durable", encoding="utf-8")
        self.assertFalse(path.exists())


class FetchGuardTests(unittest.TestCase):
    def test_https_only_and_wrong_account_host(self) -> None:
        with patch("influenzer.security.resolve_public_addresses", return_value=("93.184.216.34",)):
            with self.assertRaises(FetchError):
                validate_fetch_url("http://example.com/a", account_host="example.com")
            with self.assertRaises(FetchError):
                validate_fetch_url("https://other.example/a", account_host="example.com")
            parsed, host = validate_fetch_url("https://example.com/a", account_host="example.com")
        self.assertEqual(host, "example.com")
        self.assertEqual(parsed.path, "/a")

    def test_private_loopback_link_local_and_metadata_denied(self) -> None:
        for host in ("localhost", "127.0.0.1", "10.0.0.1", "169.254.169.254", "[::1]"):
            with self.subTest(host=host):
                with self.assertRaises(FetchError):
                    validate_fetch_url(f"https://{host}/")

    def test_oversized_payload_rejected_before_or_during_body_read(self) -> None:
        class Response:
            status = 200
            def getheader(self, name: str):
                return "text/plain" if name == "Content-Type" else "99"
            def read(self, _size: int):
                return b"x"
            def getheaders(self):
                return [("Content-Type", "text/plain")]

        class Connection:
            def __init__(self, *args, **kwargs):
                pass
            def request(self, *args, **kwargs):
                pass
            def getresponse(self):
                return Response()
            def close(self):
                pass

        with patch("influenzer.security.resolve_public_addresses", return_value=("93.184.216.34",)), \
             patch("influenzer.security._BoundHTTPSConnection", Connection):
            with self.assertRaises(FetchError):
                fetch_url("https://example.com/file", max_bytes=10)

    def test_disallowed_content_type_rejected(self) -> None:
        class Response:
            status = 200
            def getheader(self, name: str):
                return "text/html" if name == "Content-Type" else None
            def read(self, _size: int):
                return b"html"
            def getheaders(self):
                return [("Content-Type", "text/html")]

        class Connection:
            def __init__(self, *args, **kwargs):
                pass
            def request(self, *args, **kwargs):
                pass
            def getresponse(self):
                return Response()
            def close(self):
                pass

        with patch("influenzer.security.resolve_public_addresses", return_value=("93.184.216.34",)), \
             patch("influenzer.security._BoundHTTPSConnection", Connection):
            with self.assertRaises(FetchError):
                fetch_url("https://example.com/file")


if __name__ == "__main__":
    unittest.main()
