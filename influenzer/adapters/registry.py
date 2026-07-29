"""Allowlisted platform adapter handlers."""

from __future__ import annotations

from typing import Callable

from influenzer.adapters.base import AdapterRequest, AdapterResult
from influenzer.adapters.platforms import (
    bluesky_publish,
    facebook_pages_publish,
    instagram_publish,
    linkedin_publish,
    mastodon_publish,
    x_publish,
)

Handler = Callable[[AdapterRequest], AdapterResult]

ADAPTERS: dict[str, Handler] = {
    "x": x_publish,
    "bluesky": bluesky_publish,
    "mastodon": mastodon_publish,
    "linkedin": linkedin_publish,
    "instagram": instagram_publish,
    "facebook_pages": facebook_pages_publish,
}


def get_adapter(platform: str) -> Handler:
    try:
        return ADAPTERS[platform]
    except KeyError as exc:
        raise KeyError(f"unknown platform adapter: {platform}") from exc
