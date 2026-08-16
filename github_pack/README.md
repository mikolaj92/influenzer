# github_pack

Survey JSON → facts + ship/tryable flags, or silence.

Many public signals; only a ship a stranger can try becomes facts.
Tryable is a README+URL heuristic. Look does not run the project.
Launching on watch is silence. Code in look is untrusted.
Patch/typo/chore is silence. A waitlist is not a ship. A window of
merged PRs is changelog, not a tryable ship. A release without a
README+URL is not tryable. An empty repo or a repo with no README is
not a website; that is not “README without a GIF”. A private repo is not
a website, even when the owner is ours. Workshop is a public README.
README/comments/JSON
over the hard byte limit is an empty look, not a feast. 50MB in
`state.db` is silence.

Does **not**: call `gh`, write SQLite, tick, publish, or know drafts,
arenas, or `state.db`. `import github_pack` does not import Influenzer
and does not import `github_survey`.
