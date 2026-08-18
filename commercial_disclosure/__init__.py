"""Shared, dependency-free commercial-disclosure gate."""

from __future__ import annotations

import re
from collections.abc import Sequence

PAID_UNDISCLOSED_REASON = "paid_undisclosed"
_DISCLOSURE_LABELS = frozenset(
    {
        "ad",
        "advertisement",
        "advertising",
        "sponsored",
        "sponsorship",
        "paid",
        "paid partnership",
        "partner",
        "affiliate",
        "affiliate link",
        "reklama",
        "materiał reklamowy",
        "materiał sponsorowany",
        "współpraca reklamowa",
        "współpraca płatna",
        "partnerstwo płatne",
        "partnerstwo reklamowe",
        "link afiliacyjny",
    }
)
_PAID_PROMOTION_RE = re.compile(
    r"(?ix)\b(?:"
    r"paid\s+(?:promotion|partnership|partner|placement|post|content)|"
    r"partner\s+paid|"
    r"sponsor(?:ed|ship)(?:\s+(?:post|content|placement|partnership))?|"
    r"affiliate(?:s|d)?(?:\s+link(?:s)?)?|"
    r"advertis(?:e|ed|ement|ing)|reklam\w*|sponsorowan\w*|"
    r"afiliacyjn\w*|wsp[oó]łpraca\s+(?:reklamowa|p[łl]atna)|"
    r"partnerstwo\s+(?:p[łl]atne|reklamowe)|materia[łl]\s+(?:reklamowy|sponsorowany)"
    r")\b"
)
# The label must be visibly set apart from ordinary commercial copy. A phrase
# such as "affiliate link" describes the promotion but does not label it.
_INLINE_DISCLOSURE_RE = re.compile(
    r"(?ix)(?:"
    r"(?<!\w)\#(?:ad|advertisement|advertising|sponsored|paid|partner|affiliate|"
    r"reklama|wspolpraca|współpraca)\b|"
    r"\[(?:ad|advertisement|sponsored|paid|partner|affiliate|reklama)\]|"
    r"\b(?:ad|advertisement|advertising|disclosure|oznaczenie|etykieta)\s*:\s*"
    r"(?:paid|partner|affiliate|sponsored|reklama)\b"
    r")"
)


def is_disclosure_label(value: str | None) -> bool:
    """Whether one structured label is recognizable to the audience."""
    if not isinstance(value, str):
        return False
    normalized = value.strip().casefold().strip("[]#").strip()
    return normalized in _DISCLOSURE_LABELS


def has_disclosure_label(value: Sequence[str] | str | None) -> bool:
    """Whether a field or copy contains an explicit commercial disclosure."""
    if isinstance(value, str):
        return is_disclosure_label(value) or bool(_INLINE_DISCLOSURE_RE.search(value))
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        return False
    return any(is_disclosure_label(item) for item in value)


def looks_like_paid_promotion(value: str | None) -> bool:
    """Whether copy declares paid, partner, affiliate, or sponsored promotion."""
    return isinstance(value, str) and bool(_PAID_PROMOTION_RE.search(value))


def paid_disclosure_reason(value: str | None) -> str | None:
    """Fail closed when commercial copy lacks an audience-facing label."""
    if looks_like_paid_promotion(value) and not has_disclosure_label(value):
        return PAID_UNDISCLOSED_REASON
    return None


__all__ = [
    "PAID_UNDISCLOSED_REASON",
    "has_disclosure_label",
    "is_disclosure_label",
    "looks_like_paid_promotion",
    "paid_disclosure_reason",
]
