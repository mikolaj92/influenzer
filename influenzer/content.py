"""Immutable content revisions and legacy draft import."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from influenzer.domain import ContentRevision, ContentStatus, DomainError, content_hash, utc_now
from influenzer.storage import StateRepository


class ContentError(DomainError):
    pass


def create_revision(
    *,
    project_id: str,
    content_id: str,
    revision_id: str,
    body: str,
    kind: str = "post",
    source: str = "manual",
    status: ContentStatus = ContentStatus.DRAFT,
    created_at: str | None = None,
) -> ContentRevision:
    if not body.strip():
        raise ContentError("body must not be empty")
    source_digest = content_hash({"source": source, "body": body})
    return ContentRevision(
        project_id=project_id,
        content_id=content_id,
        revision_id=revision_id,
        body=body,
        kind=kind,
        status=status,
        source=source,
        source_digest=source_digest,
        created_at=created_at or utc_now(),
    ).with_hash()


def persist_revision(repo: StateRepository, revision: ContentRevision) -> ContentRevision:
    if repo.get_project(revision.project_id) is None:
        raise ContentError(f"unknown project: {revision.project_id}")
    repo.save_content_revision(revision)
    return revision


def import_legacy_card(path: str | Path, *, project_id: str) -> ContentRevision:
    """Read-only importer for old build-in-public cards.

    Maps legacy drafts to LEGACY_UNVERIFIED; never claims remote publish success.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ContentError("legacy card must be a JSON object")
    body = str(data.get("narrative") or data.get("body") or data.get("summary") or "").strip()
    if not body:
        raise ContentError("legacy card has no narrative/body")
    card_id = str(data.get("id") or data.get("card_id") or Path(path).stem)
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    return create_revision(
        project_id=project_id,
        content_id=f"legacy-{card_id}",
        revision_id=f"import-{digest}",
        body=body,
        kind="post",
        source=f"legacy:{Path(path).name}",
        status=ContentStatus.LEGACY_UNVERIFIED,
    )


def import_legacy_directory(repo: StateRepository, directory: str | Path, *, project_id: str) -> list[ContentRevision]:
    root = Path(directory)
    if not root.is_dir():
        raise ContentError(f"not a directory: {root}")
    imported: list[ContentRevision] = []
    for path in sorted(root.glob("*.json")):
        revision = import_legacy_card(path, project_id=project_id)
        persist_revision(repo, revision)
        imported.append(revision)
    return imported
