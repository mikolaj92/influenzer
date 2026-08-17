"""Survey JSON → facts + ship/tryable flags, or silence.

Does not call gh. Does not write SQLite. Does not tick. Does not publish.
Does not know drafts, arenas, or state.db. Does not load the Influenzer host.
Does not run the project. Tryable is a README+URL heuristic.
"""

from github_pack.classify import looks_like_patch_only, looks_like_ship_title
from github_pack.pack import (
    looks_like_inbound_instruction,
    looks_like_solicit_gesture,
    pack_survey,
    sanitize_inbound_facts,
    strip_inbound_instructions,
)

__all__ = [
    "looks_like_inbound_instruction",
    "looks_like_solicit_gesture",
    "looks_like_patch_only",
    "looks_like_ship_title",
    "pack_survey",
    "sanitize_inbound_facts",
    "strip_inbound_instructions",
]
