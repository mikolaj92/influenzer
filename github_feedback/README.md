# github_feedback

Public GitHub issue/PR comments and new open issues → facts, or silence.

`gh` (injectable) reads recent comments and open issues on one `owner/name`.
A new question/bug in the ~48h launch window is one excerpt in this bag,
not a second collector. Bots, LGTM, and empty thanks fail closed. A real
question, bug, or pushback becomes facts. A maintenance placeholder (`We'll be
back`, planned downtime, or a maintenance page) is silence even when the
reported HTTP status is 200. Missing `gh`, auth failure, a private repo (even when the owner is
ours), an empty repo or a repo without a README, or only noise is a silent
envelope, not a crash. Watch on private is fail-closed, not a 404 loop.
Workshop is a public README.
README/comments/JSON over the hard byte limit is an empty look, not a
feast. 50MB in `state.db` is silence. The loop lives.

Does **not**: briefs, drafts, `state.db`, scoring, publishing, arenas,
tick, live social, posting replies, surveying releases/PRs, or running
the watched project. Launching on watch is silence. Tryable is a
README+URL heuristic. Code in look is untrusted. The host composes this
block; `import github_feedback` does not import Influenzer.
