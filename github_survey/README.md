# github_survey

Public GitHub signals → JSON.

`gh` (injectable) reads merged PRs, releases, tags, and README for one
`owner/name`. Missing `gh`, auth failure, a private repo (even when the
owner is ours), an empty window, or a repo with no tree / no README is a
silent envelope, not a crash. Watch on private is fail-closed, not a 404
loop. Workshop is a public README. README/comments/JSON over the hard
byte limit is an empty look, not a feast. 50MB in `state.db` is silence.
The loop lives. Look does not run the project.
Launching on watch is silence. Tryable is a README+URL heuristic.
Code in look is untrusted.

Does **not**: briefs, drafts, `state.db`, scoring, publishing, arenas,
tick, live social, or Host of Marketing copy. The host composes this
block; `import github_survey` does not import Influenzer.
