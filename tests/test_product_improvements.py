import importlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from argparse import ArgumentParser
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def load_plugin():
    if sys.modules.get("hermes_plugins") is None:
        parent = types.ModuleType("hermes_plugins")
        parent.__path__ = []
        sys.modules["hermes_plugins"] = parent
    spec = importlib.util.spec_from_file_location(
        "hermes_plugins.build_in_public",
        PLUGIN_ROOT / "__init__.py",
        submodule_search_locations=[str(PLUGIN_ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["hermes_plugins.build_in_public"] = module
    spec.loader.exec_module(module)
    return module


class BuildPublicInitDemoTests(unittest.TestCase):
    def setUp(self):
        self.module = load_plugin()
        self.commands = self.module.commands
        self.config = importlib.import_module("hermes_plugins.build_in_public.config")
        self.card = importlib.import_module("hermes_plugins.build_in_public.card")

    def parser(self):
        parser = ArgumentParser()
        self.commands.setup_parser(parser)
        return parser

    def test_parser_registers_init_command(self):
        args = self.parser().parse_args(["--config", "config.yaml", "init"])
        self.assertEqual(args.build_in_public_command, "init")

    def test_init_bypasses_config_loading_and_writes_sample_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "config.yaml"
            notes = root / "notes"
            output = root / "output"
            args = self.parser().parse_args([
                "--config",
                str(config_path),
                "init",
                "--notes-dir",
                str(notes),
                "--output-dir",
                str(output),
            ])
            original = self.commands.load_config
            self.commands.load_config = lambda path: self.fail("init loaded config")
            try:
                result = self.commands.run_from_args(args)
            finally:
                self.commands.load_config = original
            self.assertTrue(result["ok"])
            self.assertTrue(config_path.exists())
            self.assertTrue((notes / "demo.md").exists())
            cfg = self.config.load_config(str(config_path))
            self.assertEqual(cfg.output_mode, "draft-only")
            self.assertFalse(cfg.publish.get("enabled"))
            self.assertTrue(cfg.sources.manual.enabled)
            self.assertEqual(Path(cfg.sources.manual.path), notes)

    def test_init_refuses_to_overwrite_existing_config_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.yaml"
            target.write_text("version: 1\n")
            args = self.parser().parse_args(["--config", str(target), "init"])
            with self.assertRaises(self.config.ConfigError):
                self.commands.run_from_args(args)

    def test_root_config_example_is_loadable_and_safe(self):
        example = PLUGIN_ROOT / "config.example.yaml"
        self.assertTrue(example.exists())
        cfg = self.config.load_config(str(example))
        self.assertEqual(cfg.output_mode, "draft-only")
        self.assertFalse(cfg.publish.get("enabled"))
        self.assertTrue(cfg.sources.manual.enabled)

    def test_docs_and_ci_are_present_for_three_minute_path(self):
        readme = (PLUGIN_ROOT / "README.md").read_text()
        after_install = PLUGIN_ROOT / "after-install.md"
        ci = PLUGIN_ROOT / ".github" / "workflows" / "ci.yml"
        self.assertTrue(after_install.exists())
        self.assertTrue(ci.exists())
        self.assertIn("init", readme)
        self.assertIn("install", readme.lower())
        self.assertIn("checks", ci.read_text().lower())

    def test_init_sample_demo_flow_creates_card_draft_and_weekly_recap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "config.yaml"
            args = self.parser().parse_args([
                "--config",
                str(config_path),
                "init",
                "--notes-dir",
                str(root / "notes"),
                "--output-dir",
                str(root / "output"),
            ])
            self.commands.run_from_args(args)
            cfg = self.config.load_config(str(config_path))
            collected = self.commands.collect(cfg, live_flag=True, source="manual", limit=10)
            rendered = self.commands.render(cfg, live_flag=True, format_name="all")
            weekly = self.commands.weekly_recap(cfg, live_flag=True, week="2026-W01")
            card_paths = sorted((root / "output" / "cards").glob("*.json"))
            draft_paths = sorted((root / "output" / "drafts").glob("*.md"))
            weekly_path = root / "output" / "weekly" / "2026-W01.md"
            self.assertEqual(collected["count"], 1)
            self.assertEqual(rendered["count"], 1)
            self.assertTrue(weekly["written"])
            self.assertEqual(len(card_paths), 1)
            self.assertEqual(len(draft_paths), 1)
            self.assertTrue(weekly_path.exists())
            card = json.loads(card_paths[0].read_text())
            self.card.validate_card(card)
            self.assertIn("## Short draft", draft_paths[0].read_text())
            self.assertIn("Demo Project", weekly_path.read_text())


if __name__ == "__main__":
    unittest.main()
