"""Public GitHub issue/PR comments and new open issues → facts, or silence.

Does not know briefs, drafts, state.db, scoring, publishing, or arenas.
Does not write SQLite. Does not tick. Does not load the Influenzer host.
Does not post replies. Does not survey releases/PRs. Does not enable live.
Does not know Heimdall. Does not know my-auth. Does not scrape X/LinkedIn.
"""

from github_feedback.feedback import collect_feedback, is_feedback_signal, is_noise_comment
from github_pack.pack import (
    looks_like_inbound_instruction,
    sanitize_inbound_facts,
    strip_inbound_instructions,
)

__all__ = [
    "collect_feedback",
    "is_feedback_signal",
    "is_noise_comment",
    "looks_like_inbound_instruction",
    "sanitize_inbound_facts",
    "strip_inbound_instructions",
]
