# github_feedback

Public GitHub issue/PR comments → facts, or silence.

`gh` (injectable) reads recent comments on one `owner/name`. Bots, LGTM,
and empty thanks fail closed. A real question, bug, or pushback becomes
facts. Missing `gh`, auth failure, a private repo, an empty repo or a repo
without a README, or only noise is a silent envelope, not a crash.
README/comments/JSON over the hard byte limit is an empty look, not a
feast. 50MB in `state.db` is silence. The loop lives.

Does **not**: briefs, drafts, `state.db`, scoring, publishing, arenas,
tick, live social, posting replies, surveying releases/PRs, or running
the watched project. Launching on watch is silence. Tryable is a
README+URL heuristic. Code in look is untrusted. The host composes this
block; `import github_feedback` does not import Influenzer.
