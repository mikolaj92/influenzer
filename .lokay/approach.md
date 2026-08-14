# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=132 -->

Repository: `mikolaj92/influenzer`  
Issue: #132 — Prywatna rozmowa nie idzie w kąt

## Goal

Prywatna rozmowa nie idzie w kąt. Zrzut Slacka, maila, DMa w body = cisza. Nawet „anonimizowane”. To nie excerpt z publicznego issue.

Fail-closed:
- Slack / mail / DM in body = silence, even after anonymization.
- Excerpt only from a public GitHub issue/PR comment.

## Files likely touched

- `influenzer/playbook.py` — private-channel host set, dump detector, public-issue excerpt URL
- `influenzer/hom.py` — score Slack/mail/DM dumps as kill
- `influenzer/hom_draft.py` — refuse to dress a leaked private conversation
- `tests/test_hom_operator.py` — detector + score kills
- `tests/test_hom_draft.py` — undressable even when score says draft

## Test plan

- `python -m pytest tests/test_hom_operator.py tests/test_hom_draft.py tests/test_hom_feedback.py tests/test_github_feedback.py -q`

## Non-goals

- Do not scrape Slack, mail, or DMs.
- Do not treat a Slack/webmail URL as a legal excerpt source.
- Do not kill product talk such as a Slack integration or a support inbox.

## Notes

- Neighbors: #47 (secret does not leave) and #119 (quote only from feedback with a URL). This issue is the channel, not the token.
- A Slack / Gmail / Outlook host is not a public issue. Anonymized still counts.
- Trust intentional issue; this plan is evidence for later review, not a human gate.
