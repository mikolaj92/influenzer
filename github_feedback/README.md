# github_feedback

Public GitHub issue/PR comments → facts, or silence.

`gh` (injectable) reads recent comments on one `owner/name`. Bots, LGTM,
and empty thanks fail closed. A real question, bug, or pushback becomes
facts. Missing `gh`, auth failure, a private repo, or only noise is a
silent envelope, not a crash.

Does **not**: briefs, drafts, `state.db`, scoring, publishing, arenas,
tick, live social, posting replies, or surveying releases/PRs. The host
composes this block; `import github_feedback` does not import Influenzer.
