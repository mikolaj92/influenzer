from __future__ import annotations

import importlib.util
import sys
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
        parent.__path__ = []  # type: ignore[attr-defined]
        sys.modules["hermes_plugins"] = parent
    name = "hermes_plugins.influenzer"
    path = PLUGIN_ROOT / "__init__.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    if str(PLUGIN_ROOT) not in sys.path:
        sys.path.insert(0, str(PLUGIN_ROOT))
    spec.loader.exec_module(module)
    return module


class PluginRegistrationTests(unittest.TestCase):
    def test_register_uses_influenzer_cli_and_skills(self) -> None:
        module = load_plugin()
        ctx = StubContext()
        module.register(ctx)
        self.assertEqual(ctx.cli_commands[0][0], "influenzer")
        skill_names = [name for name, _path, _desc in ctx.skills]
        self.assertEqual(
            skill_names,
            [
                "influenzer-profile",
                "influenzer-content",
                "influenzer-campaign",
                "influenzer-publish",
                "influenzer-hom",
            ],
        )
        for _name, path, _desc in ctx.skills:
            self.assertTrue(path.exists(), path)

    def test_cli_parser_registers_subcommands(self) -> None:
        from influenzer import cli

        parser = ArgumentParser()
        cli.setup_parser(parser)
        args = parser.parse_args(
            [
                "project",
                "create",
                "--id",
                "a",
                "--slug",
                "a",
                "--name",
                "A",
                "--display-name",
                "A",
                "--voice",
                "v",
                "--audience",
                "x",
                "--maintainer",
                "m",
            ]
        )
        self.assertEqual(args.command, "project")
        self.assertEqual(args.project_command, "create")


if __name__ == "__main__":
    unittest.main()
