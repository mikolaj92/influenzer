# build-in-public Hermes plugin

`build-in-public` turns project activity into local draft artifacts: build cards, short post drafts, thread drafts, and weekly recap notes. It is intentionally separate from repo automation and never publishes to social networks in v0.

## Install

```bash
hermes plugins install mikolaj92/hermes-plugin-build-in-public --enable
```

This repository is a standalone Hermes plugin: `plugin.yaml` and `__init__.py`
live at the repository root.

## Configure

Default config path:

```text
~/.hermes/build-in-public/config.yaml
```

Override it with `--config PATH` or `HERMES_BUILD_IN_PUBLIC_CONFIG`.

Start from `examples/config.example.yaml`. Keep real notes and generated output outside the repository you publish.

## Commands

```bash
hermes build-in-public validate --config config.yaml
hermes build-in-public collect --config config.yaml --source manual
hermes build-in-public collect --config config.yaml --source manual --live
hermes build-in-public render --config config.yaml --format all --live
hermes build-in-public weekly-recap --config config.yaml --live
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
