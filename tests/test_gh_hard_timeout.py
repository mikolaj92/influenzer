from __future__ import annotations

import os
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

from github_survey import GhCall, run_gh
from github_survey.survey import look_short_gh
from influenzer.brief_scan import look_hard_gh
from influenzer.tick import loop_ticks


class HardGhTimeoutTests(unittest.TestCase):
    def test_entered_spawn_cannot_block_deadline(self) -> None:
        entered = threading.Event()
        release = threading.Event()
        returned = threading.Event()
        finished = threading.Event()
        children = []
        results = []
        popen = subprocess.Popen

        def spawn(argv, **kwargs):
            entered.set()
            release.wait()
            child = popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
            children.append(child)
            return child

        def inner(argv):
            try:
                return run_gh(argv)
            finally:
                finished.set()

        def call():
            results.append(look_hard_gh(inner, timeout_s=0.1)(["repo", "view", "owner/name"]))
            returned.set()

        with patch("github_survey.gh.subprocess.Popen", side_effect=spawn):
            caller = threading.Thread(target=call)
            caller.start()
            try:
                self.assertTrue(entered.wait(2))
                self.assertTrue(returned.wait(0.5), "deadline blocked by entered Popen")
            finally:
                release.set()
                caller.join(2)
                self.assertTrue(finished.wait(2))
        self.assertEqual(results[0].returncode, 124)
        self.assertEqual(children[0].returncode, -9)

    def test_blocked_reaping_cannot_block_deadline(self) -> None:
        release = threading.Event()
        entered = threading.Event()
        returned = threading.Event()
        finished = threading.Event()
        from github_survey.gh import _kill_gh_child
        popen = subprocess.Popen

        def spawn(argv, **kwargs):
            return popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)

        def blocked_cleanup(child):
            entered.set()
            release.wait()
            _kill_gh_child(child)

        def inner(argv):
            try:
                return run_gh(argv)
            finally:
                finished.set()

        def call():
            look_hard_gh(inner, timeout_s=0.1)(["repo", "view", "owner/name"])
            returned.set()

        with patch("github_survey.gh.subprocess.Popen", side_effect=spawn), patch(
            "github_survey.gh._kill_gh_child", side_effect=blocked_cleanup,
        ):
            caller = threading.Thread(target=call)
            caller.start()
            try:
                self.assertTrue(entered.wait(2))
                self.assertTrue(returned.wait(0.5))
            finally:
                release.set()
                caller.join(2)
                self.assertTrue(finished.wait(2))

    def test_communication_exception_cleans_actual_child(self) -> None:
        for error in (OSError("pipe failure"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                children = []
                popen = subprocess.Popen

                def spawn(argv, **kwargs):
                    child = popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
                    children.append(child)
                    child.communicate = lambda **kw: (_ for _ in ()).throw(error)
                    return child

                try:
                    with patch("github_survey.gh.subprocess.Popen", side_effect=spawn):
                        if isinstance(error, OSError):
                            self.assertEqual(run_gh(["repo", "view", "owner/name"]).returncode, 127)
                        else:
                            with self.assertRaises(KeyboardInterrupt):
                                run_gh(["repo", "view", "owner/name"])
                    self.assertIsNotNone(children[0].returncode)
                    self.assertTrue(children[0].stdout.closed)
                    self.assertTrue(children[0].stderr.closed)
                finally:
                    for child in children:
                        child.kill()
                        child.wait()
                        child.stdout.close()
                        child.stderr.close()

    def test_wrapped_real_child_is_killed_reaped_and_isolated(self) -> None:
        children = []
        popen = subprocess.Popen

        def spawn(argv, **kwargs):
            child = popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
            children.append(child)
            self.assertEqual(os.getpgid(child.pid), child.pid)
            self.assertNotEqual(os.getpgid(child.pid), os.getpgrp())
            return child

        finished = threading.Event()

        def inner(argv):
            try:
                return run_gh(argv)
            finally:
                finished.set()

        runner = look_hard_gh(look_short_gh(inner), timeout_s=0.2)
        try:
            with patch("github_survey.gh.subprocess.Popen", side_effect=spawn):
                call = runner(["repo", "view", "owner/name"])
            self.assertEqual(call.returncode, 124)
            self.assertEqual(len(children), 1)
            self.assertTrue(finished.wait(2))
            self.assertEqual(children[0].returncode, -9)
            with self.assertRaises(ChildProcessError):
                os.waitpid(children[0].pid, os.WNOHANG)
        finally:
            # The timeout reaps synchronously, but the worker still owns its
            # pipes. Never race a second communicate against that worker.
            for child in children:
                if child.poll() is None:
                    child.kill()
            self.assertTrue(finished.wait(2))

    def test_timeout_does_not_kill_concurrent_unrelated_call(self) -> None:
        popen = subprocess.Popen
        started = threading.Event()
        result = []

        def spawn(argv, **kwargs):
            delay = 60 if argv[2] == "owner/hung" else 0.5
            child = popen(
                [sys.executable, "-c", f"import time; time.sleep({delay}); print('ok')"],
                **kwargs,
            )
            if delay != 60:
                started.set()
            return child

        def unrelated():
            result.append(run_gh(["repo", "view", "owner/other"], timeout=2))

        with patch("github_survey.gh.subprocess.Popen", side_effect=spawn):
            worker = threading.Thread(target=unrelated)
            worker.start()
            try:
                self.assertTrue(started.wait(2))
                call = look_hard_gh(timeout_s=0.1)(["repo", "view", "owner/hung"])
                self.assertEqual(call.returncode, 124)
            finally:
                worker.join(3)
            self.assertFalse(worker.is_alive())
        self.assertEqual(result[0].returncode, 0)
        self.assertEqual(result[0].stdout.strip(), "ok")

    def test_native_timeout_reaps_child(self) -> None:
        children = []
        popen = subprocess.Popen

        def spawn(argv, **kwargs):
            child = popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
            children.append(child)
            return child

        with patch("github_survey.gh.subprocess.Popen", side_effect=spawn):
            call = run_gh(["repo", "view", "owner/name"], timeout=0.1)
        self.assertEqual(call.returncode, 124)
        self.assertEqual(children[0].returncode, -9)
        with self.assertRaises(ChildProcessError):
            os.waitpid(children[0].pid, os.WNOHANG)

    def test_cancelled_worker_cannot_spawn_after_deadline(self) -> None:
        release = threading.Event()
        finished = threading.Event()
        results = []

        def inner(argv):
            release.wait()
            try:
                results.append(run_gh(argv))
                return results[-1]
            finally:
                finished.set()

        with patch("github_survey.gh.subprocess.Popen") as spawn:
            try:
                call = look_hard_gh(inner, timeout_s=0.1)(["repo", "view", "owner/name"])
                self.assertEqual(call.returncode, 124)
            finally:
                release.set()
                self.assertTrue(finished.wait(2))
            spawn.assert_not_called()
        self.assertEqual(results[0].returncode, 124)

    def test_hung_inner_does_not_signal_host_and_next_tick_runs(self) -> None:
        release = threading.Event()
        finished = threading.Event()
        calls = 0

        def inner(argv):
            nonlocal calls
            calls += 1
            if calls == 1:
                try:
                    release.wait()
                finally:
                    finished.set()
            return GhCall(0, "ok")

        runner = look_hard_gh(inner, timeout_s=0.1)
        try:
            with patch("os.killpg") as killpg:
                results = loop_ticks(
                    lambda: {"code": runner(["repo", "view", "owner/name"]).returncode},
                    interval=1, max_ticks=2, sleep=lambda _: None,
                )
                self.assertEqual([r["code"] for r in results], [124, 0])
                killpg.assert_not_called()
        finally:
            release.set()
            self.assertTrue(finished.wait(2))
