"""Immutable content revisions (single modern path via create_revision)."""

from __future__ import annotations

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
