from __future__ import annotations

import re


TOKEN_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"Authorization:\s*Bearer\s+\S+", re.I),
    re.compile(r"xoxb-[A-Za-z0-9-]+"),
    re.compile(r"sk-[A-Za-z0-9][A-Za-z0-9_-]{12,}"),
    re.compile("/" + r"Users/[A-Za-z0-9._-]+(?:/[^\s`\"]*)?"),
)


def redact_text(value: str) -> str:
    redacted = value
    for pattern in TOKEN_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted
