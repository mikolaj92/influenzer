# build-in-public Hermes plugin

Local draft generator for build-in-public notes.

`build-in-public` turns a local Markdown note into build-card JSON, draft Markdown, and a weekly recap. It is intentionally separate from repo automation and never publishes to social networks in v0.

## Install

```bash
hermes plugins install mikolaj92/hermes-plugin-build-in-public --enable
```

This repository is a standalone Hermes plugin: `plugin.yaml` and `__init__.py`
live at the repository root.

After install, Hermes may show [`after-install.md`](after-install.md). The short version is: create the sample config and note, collect the note, render drafts, then read the generated local files.

## 3-minute local demo

```bash
hermes build-in-public --config config.yaml init
hermes build-in-public --config config.yaml validate
hermes build-in-public --config config.yaml collect --source manual --live
hermes build-in-public --config config.yaml render --format all --live
hermes build-in-public --config config.yaml weekly-recap --live
```

`--live` means local file writes only for this plugin. It does not publish anywhere.

## Configure

Default config path:

```text
~/.hermes/build-in-public/config.yaml
```

Override it with `--config PATH` or `HERMES_BUILD_IN_PUBLIC_CONFIG`.

Start from `config.example.yaml`, or run `init` to create `config.yaml` and `notes/demo.md`. Keep real notes and generated output outside the repository you publish.

## Commands

```bash
hermes build-in-public --config config.yaml init
hermes build-in-public --config config.yaml validate
hermes build-in-public --config config.yaml collect --source manual
hermes build-in-public --config config.yaml collect --source manual --live
hermes build-in-public --config config.yaml render --format all --live
hermes build-in-public --config config.yaml weekly-recap --live
```

Without `--live`, commands plan work and do not write files. With `--live`, v0 still writes only local files under the configured `output_dir`.

## Output

```text
output_dir/
  cards/<stable-id>.json
  drafts/<stable-id>.md
  weekly/YYYY-WW.md
```

Stable IDs include source kind, repo slug, event kind, date or number, and a short content hash. Running collection twice over the same input overwrites the same file instead of creating duplicates.

## Safety

- `output_mode` must be `draft-only`.
- `publish.enabled` must be `false` or absent.
- Social credential keys are rejected by config validation.
- `render` and `weekly-recap` read local cards only.
- Hook ingestion is optional; command-based collection is the primary path.
- Generated drafts are review material, not publishing instructions.

## Skills

The plugin registers bare skill names with Hermes. Load them by qualified name when needed:

- `build-in-public:build-card-capture`
- `build-in-public:build-card-to-x-post`
- `build-in-public:build-card-to-thread`
- `build-in-public:build-card-to-weekly-recap`
- `build-in-public:maintainer-narrative-policy`
