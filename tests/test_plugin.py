from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from argparse import ArgumentParser
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class StubContext:
    def __init__(self) -> None:
        self.cli_commands = []
        self.skills = []
        self.hooks = []

    def register_cli_command(self, name, help, setup_fn, handler_fn=None, description=""):
        self.cli_commands.append((name, help, setup_fn, handler_fn, description))

    def register_skill(self, name, path, description=""):
        if ":" in name:
            raise AssertionError("skill names must be bare")
        self.skills.append((name, Path(path), description))

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))


def load_plugin():
    parent = sys.modules.get("hermes_plugins")
    if parent is None:
        parent = types.ModuleType("hermes_plugins")
        parent.__path__ = []
        sys.modules["hermes_plugins"] = parent
    module_name = "hermes_plugins.build_in_public"
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / "__init__.py", submodule_search_locations=[str(PLUGIN_ROOT)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class PluginRegistrationTests(unittest.TestCase):
    def test_register_uses_bare_skills_and_hook(self):
        module = load_plugin()
        ctx = StubContext()
        module.register(ctx)
        self.assertEqual(ctx.cli_commands[0][0], "build-in-public")
        self.assertEqual({name for name, _, _ in ctx.skills}, {
            "build-card-capture",
            "build-card-to-x-post",
            "build-card-to-thread",
            "build-card-to-weekly-recap",
            "maintainer-narrative-policy",
        })
        for _, path, _ in ctx.skills:
            self.assertTrue(path.exists())
        self.assertEqual(ctx.hooks[0][0], "kanban_task_completed")

    def test_cli_parser_registers_subcommands(self):
        module = load_plugin()
        parser = ArgumentParser()
        module.commands.setup_parser(parser)
        args = parser.parse_args(["--config", "config.json", "validate"])
        self.assertEqual(args.build_in_public_command, "validate")


class BuildInPublicTests(unittest.TestCase):
    def setUp(self):
        load_plugin()

    def config_file(self, root: Path, notes: Path) -> Path:
        cfg = {
            "version": 1,
            "output_mode": "draft-only",
            "output_dir": str(root / "out"),
            "audience": "maintainers",
            "sources": {"manual": {"enabled": True, "path": str(notes)}},
            "publish": {"enabled": False},
        }
        path = root / "config.json"
        path.write_text(json.dumps(cfg), encoding="utf-8")
        return path

    def test_config_rejects_publish_and_social_credentials(self):
        from hermes_plugins.build_in_public.config import BuildInPublicConfig, ConfigError

        with self.assertRaises(ConfigError):
            BuildInPublicConfig.from_mapping({"output_mode": "draft-only", "publish": {"enabled": True}})
        key = "_".join(("x", "api", "key"))
        with self.assertRaises(ConfigError):
            BuildInPublicConfig.from_mapping({"output_mode": "draft-only", "publish": {"enabled": False, key: "nope"}})

    def test_manual_collect_is_deterministic_and_idempotent(self):
        from hermes_plugins.build_in_public.commands import collect
        from hermes_plugins.build_in_public.config import load_config
        from hermes_plugins.build_in_public.storage import load_cards

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes = root / "notes"
            notes.mkdir()
            (notes / "one.md").write_text("# ReviewKit\n\nChose a smaller API surface.", encoding="utf-8")
            cfg = load_config(self.config_file(root, notes))
            dry = collect(cfg, live_flag=False, source="manual", limit=10)
            self.assertFalse(dry["effective_write"])
            first = collect(cfg, live_flag=True, source="manual", limit=10)
            second = collect(cfg, live_flag=True, source="manual", limit=10)
            self.assertEqual(first["planned_ids"], second["planned_ids"])
            self.assertEqual(len(load_cards(cfg.output_path())), 1)

    def test_render_and_weekly_only_write_live(self):
        from hermes_plugins.build_in_public.commands import collect, render, weekly_recap
        from hermes_plugins.build_in_public.config import load_config

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes = root / "notes"
            notes.mkdir()
            (notes / "one.md").write_text("# Fala\n\nChanged retry semantics.", encoding="utf-8")
            cfg = load_config(self.config_file(root, notes))
            collect(cfg, live_flag=True, source="manual", limit=10)
            dry_render = render(cfg, live_flag=False, format_name="all")
            self.assertEqual(dry_render["written"], [])
            live_render = render(cfg, live_flag=True, format_name="all")
            self.assertTrue(live_render["written"])
            dry_weekly = weekly_recap(cfg, live_flag=False, week="2026-W01")
            self.assertIsNone(dry_weekly["written"])
            live_weekly = weekly_recap(cfg, live_flag=True, week="2026-W01")
            self.assertTrue(Path(live_weekly["written"]).exists())

    def test_schema_and_internal_validator(self):
        from hermes_plugins.build_in_public.card import validate_card
        from hermes_plugins.build_in_public.collector import event_to_card
        from hermes_plugins.build_in_public.config import BuildInPublicConfig

        schema = json.loads((PLUGIN_ROOT / "schemas" / "build-card.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["additionalProperties"], False)
        card = event_to_card({"project": "Demo", "event": "ship", "problem": "Bug", "decision": "Fix"}, BuildInPublicConfig())
        validate_card(card.to_dict())
        broken = card.to_dict()
        broken["extra"] = "nope"
        with self.assertRaises(Exception):
            validate_card(broken)

    def test_modules_do_not_import_network_or_subprocess(self):
        for name in ("collector.py", "commands.py", "renderer.py", "storage.py", "card.py", "config.py"):
            text = (PLUGIN_ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("subprocess", text)
            self.assertNotIn("urllib", text)
            self.assertNotIn("socket", text)


if __name__ == "__main__":
    unittest.main()
