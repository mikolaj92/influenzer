from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from influenzer.cli import main as cli_main
from influenzer.config import (
    PERMISSION_REFUSED,
    Config,
    WorkspacePermissionError,
    open_workspace,
    write_config,
)
from influenzer.storage import StateRepository
from influenzer.tick import main as tick_main
from influenzer.tick_all import main as tick_all_main
from tests.test_tick_loop import ALWAYS_ON, _project


class WorkspacePermissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "ws"
        self.config = self.home / "config.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _init(self) -> None:
        self.assertEqual(cli_main(["--config", str(self.config), "init", "--home", str(self.home)]), 0)

    def test_init_makes_home_0700_and_files_0600(self) -> None:
        self._init()
        self.assertEqual(self.home.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.home / "state.db").stat().st_mode & 0o777, 0o600)
        for sidecar in ("-wal", "-shm"):
            path = Path(str(self.home / "state.db") + sidecar)
            if path.exists():
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_open_workspace_refuses_world_readable_home(self) -> None:
        self._init()
        os.chmod(self.home, 0o755)
        with self.assertRaises(WorkspacePermissionError):
            open_workspace(str(self.config))

    def test_open_workspace_refuses_world_readable_config(self) -> None:
        self._init()
        os.chmod(self.config, 0o644)
        with self.assertRaises(WorkspacePermissionError):
            open_workspace(str(self.config))

    def test_open_workspace_refuses_world_readable_state_db(self) -> None:
        self._init()
        os.chmod(self.home / "state.db", 0o644)
        with self.assertRaises(WorkspacePermissionError):
            open_workspace(str(self.config))

    def test_cli_is_silence_when_home_is_too_open(self) -> None:
        self._init()
        os.chmod(self.home, 0o755)
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = cli_main(["--config", str(self.config), "watch", "show"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout.getvalue()), PERMISSION_REFUSED)

    def test_tick_all_is_silence_when_config_is_too_open(self) -> None:
        self._init()
        os.chmod(self.config, 0o644)
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = tick_all_main(["--config", str(self.config)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout.getvalue()), PERMISSION_REFUSED)

    def test_interval_tick_is_silence_when_state_db_is_too_open(self) -> None:
        write_config(self.config, Config(home=self.home))
        with StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo:
            _project(repo)
        os.chmod(self.home / "state.db", 0o644)
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = tick_main(
                ["--config", str(self.config), "--interval", "300"],
                inspect_host=lambda: ALWAYS_ON,
            )
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout.getvalue()), PERMISSION_REFUSED)

    def test_group_readable_is_also_too_open(self) -> None:
        self._init()
        os.chmod(self.config, 0o640)
        with self.assertRaises(WorkspacePermissionError):
            open_workspace(str(self.config))


if __name__ == "__main__":
    unittest.main()
