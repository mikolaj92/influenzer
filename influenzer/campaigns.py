"""Organic and paid campaign planning without spend mutation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from influenzer.domain import Campaign, CampaignKind, CampaignStatus, DomainError
from influenzer.storage import StateRepository


class CampaignError(DomainError):
    pass


# No Ads/Marketing API write path exists. Paid campaigns are plan/export only.
SPEND_PATHS = frozenset()


def create_campaign(
    *,
    project_id: str,
    campaign_id: str,
    name: str,
    kind: str | CampaignKind = CampaignKind.ORGANIC,
    budget_amount: float | None = None,
    budget_currency: str | None = None,
    disclosures: tuple[str, ...] = (),
    status: CampaignStatus = CampaignStatus.DRAFT,
) -> Campaign:
    campaign = Campaign(
        project_id=project_id,
        campaign_id=campaign_id,
        kind=CampaignKind(kind) if not isinstance(kind, CampaignKind) else kind,
        name=name,
        status=status,
        budget_amount=budget_amount,
        budget_currency=budget_currency,
        disclosures=disclosures,
    )
    campaign.validate()
    return campaign


def persist_campaign(repo: StateRepository, campaign: Campaign) -> Campaign:
    if repo.get_project(campaign.project_id) is None:
        raise CampaignError(f"unknown project: {campaign.project_id}")
    if campaign.kind is CampaignKind.PAID and SPEND_PATHS:
        raise CampaignError("paid spend path is forbidden")
    repo.save_campaign(campaign)
    return campaign


def export_campaign_plan(campaign: Campaign, path: str | Path) -> Path:
    """Write a planning artifact. Never includes spend API calls or credentials."""
    target = Path(path)
    payload: dict[str, Any] = {
        "project_id": campaign.project_id,
        "campaign_id": campaign.campaign_id,
        "kind": campaign.kind.value,
        "name": campaign.name,
        "status": campaign.status.value,
        "budget_amount": campaign.budget_amount,
        "budget_currency": campaign.budget_currency,
        "disclosures": list(campaign.disclosures),
        "executable_spend": False,
        "note": "planning/export only; no Ads API mutation path",
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target
