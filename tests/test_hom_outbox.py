from __future__ import annotations

import io
import json
import tomllib
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from influenzer.cli import main as cli_main
from influenzer.config import Config, write_config
from influenzer.domain import Project
from influenzer.hom import Brief, Draft, Fact, Score
from influenzer.hom_outbox import emit_angle, is_wearable, main as outbox_main
from influenzer.playbook import ARENAS, ArenaId, StoryKind, Verdict
from influenzer.storage import StateRepository

from tests.test_hom_operator import SHIP_PR


def _import_lines(path: Path) -> list[str]:
    found: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            found.append(stripped)
    return found


def _project(repo: StateRepository, project_id: str = "app-1") -> None:
    repo.save_project(
        Project.create(
            project_id=project_id,
            slug=project_id.replace("-", ""),
            name="App",
            display_name="App",
            voice="product",
            audience="builders",
            maintainer="mikolaj92",
            kind="app",
        )
    )


def _put_draft(
    repo: StateRepository,
    *,
    project_id: str,
    brief_id: str,
    created_at: str,
    body: str,
    arena: ArenaId = ArenaId.HN,
) -> Draft:
    play = ARENAS[arena]
    brief = Brief.create(
        project_id=project_id,
        brief_id=brief_id,
        facts=(Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),),
        story_kind=StoryKind.MAJOR,
        claims_ship=True,
        tryable=True,
        preferred_arena=arena,
        created_at=created_at,
    )
    repo.save_brief(brief)
    score = Score(
        brief_id=brief_id,
        verdict=Verdict.DRAFT,
        reason="one_angle",
        arena=arena,
        angle="what shipped and why a stranger should try it",
        wave_checklist=play.wave,
        canon_url=play.canon_url,
    ).with_hash()
    draft = Draft(
        project_id=project_id,
        brief_id=brief_id,
        draft_id=f"draft-{brief_id}",
        arena=arena,
        costume=play.costume,
        angle=score.angle or "",
        body=body,
        wave_checklist=play.wave,
        canon_url=play.canon_url,
        created_at=created_at,
    ).with_hash()
    repo.persist_operator_decision(brief, score, draft, now=created_at)
    return draft


def _put_kill(repo: StateRepository, *, brief_id: str, created_at: str) -> None:
    brief = Brief.create(
        project_id="app-1",
        brief_id=brief_id,
        facts=(Fact(text="we shipped it"),),
        story_kind=StoryKind.MAJOR,
        claims_ship=True,
        tryable=True,
        created_at=created_at,
    )
    repo.save_brief(brief)
    score = Score(
        brief_id=brief_id,
        verdict=Verdict.KILL,
        reason="ship_claim_missing_artifact",
        arena=None,
        angle=None,
        wave_checklist=(),
        canon_url=ARENAS[ArenaId.HN].canon_url,
    ).with_hash()
    repo.persist_operator_decision(brief, score, None, now=created_at)


def _put_changelog(repo: StateRepository, *, brief_id: str, created_at: str) -> None:
    brief = Brief.create(
        project_id="app-1",
        brief_id=brief_id,
        facts=(Fact(text="typo in README"),),
        story_kind=StoryKind.PATCH,
        created_at=created_at,
    )
    repo.save_brief(brief)
    score = Score(
        brief_id=brief_id,
        verdict=Verdict.CHANGELOG_ONLY,
        reason="patch_is_changelog",
        arena=None,
        angle=None,
        wave_checklist=(),
        canon_url=ARENAS[ArenaId.GITHUB].canon_url,
    ).with_hash()
    repo.persist_operator_decision(brief, score, None, now=created_at)


class HomOutboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.cfg = Config(home=self.home, scheduler_live_enabled=False)
        write_config(self.home / "config.json", self.cfg)
        self.repo = StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts")
        _project(self.repo)

    def tearDown(self) -> None:
        self.repo.close()
        self.tmp.cleanup()

    def _snapshot_drafts(self) -> list[tuple[str, str, str]]:
        return [
            (row["draft_id"], row["body"], row["content_hash"])
            for row in self.repo.conn.execute(
                "SELECT draft_id, body, content_hash FROM operator_drafts ORDER BY created_at, draft_id"
            )
        ]

    def test_no_draft_is_silence(self) -> None:
        with patch("subprocess.run", side_effect=AssertionError("outbox must not call subprocess")):
            out = emit_angle(self.repo)
        self.assertEqual(out["status"], "noop")
        self.assertTrue(out["ok"])
        self.assertTrue(out["empty"])
        self.assertEqual(out["reason"], "no_draft")
        self.assertIsNone(out["body"])
        self.assertIsNone(out["draft_id"])
        self.assertFalse(out["published"])
        self.assertFalse(out["mutated"])

    def test_kill_and_changelog_are_silence(self) -> None:
        _put_kill(self.repo, brief_id="kill-1", created_at="2026-08-13T04:00:00Z")
        _put_changelog(self.repo, brief_id="patch-1", created_at="2026-08-13T04:01:00Z")
        out = emit_angle(self.repo, project_id="app-1")
        self.assertEqual(out["status"], "noop")
        self.assertTrue(out["empty"])
        self.assertEqual(out["reason"], "no_draft")
        self.assertFalse(out["published"])

    def test_one_wearable_draft_is_one_packet_not_a_costume_prefix(self) -> None:
        body = f"Show HN: Local tick scores briefs\n\n{SHIP_PR}"
        draft = _put_draft(
            self.repo,
            project_id="app-1",
            brief_id="b-ship",
            created_at="2026-08-13T05:00:00Z",
            body=body,
        )
        before = self._snapshot_drafts()
        with patch("subprocess.run", side_effect=AssertionError("outbox must not call subprocess")):
            out = emit_angle(self.repo, project_id="app-1")
        self.assertEqual(out["status"], "ok")
        self.assertFalse(out["empty"])
        self.assertEqual(out["draft_id"], draft.draft_id)
        self.assertEqual(out["brief_id"], "b-ship")
        self.assertEqual(out["project_id"], "app-1")
        self.assertEqual(out["arena"], "hn")
        self.assertEqual(out["costume"], "seminar")
        self.assertEqual(out["angle"], "what shipped and why a stranger should try it")
        self.assertEqual(out["body"], body)
        self.assertEqual(out["content_hash"], draft.content_hash)
        self.assertEqual(out["canon_url"], draft.canon_url)
        self.assertFalse(out["body"].startswith("Costume:"))
        self.assertNotIn("Costume:", out["body"])
        self.assertNotIn("One arena:", out["body"])
        self.assertFalse(out["published"])
        self.assertFalse(out["mutated"])
        self.assertEqual(self._snapshot_drafts(), before)
        self.assertFalse(json.loads((self.home / "config.json").read_text(encoding="utf-8"))["scheduler"]["live_enabled"])

    def test_same_body_across_arenas_is_silence_and_not_saved_twice(self) -> None:
        body = f"same wearable body\n\n{SHIP_PR}"
        first = _put_draft(
            self.repo,
            project_id="app-1",
            brief_id="hn-first",
            created_at="2026-08-13T05:00:00Z",
            body=body,
            arena=ArenaId.HN,
        )
        second = _put_draft(
            self.repo,
            project_id="app-1",
            brief_id="github-second",
            created_at="2026-08-13T06:00:00Z",
            body=body,
            arena=ArenaId.GITHUB,
        )
        self.assertEqual(len(self.repo.list_operator_drafts("app-1")), 1)
        self.assertEqual(self.repo.list_operator_drafts("app-1")[0].draft_id, first.draft_id)
        score = self.repo.get_operator_score("app-1", "github-second")
        assert score is not None
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "same_body_other_arena")
        self.assertIsNone(self.repo.get_operator_draft("app-1", "github-second"))
        self.assertEqual(second.content_hash, first.content_hash)

    def test_two_drafts_still_one_packet_newest_wearable(self) -> None:
        _put_draft(
            self.repo,
            project_id="app-1",
            brief_id="older",
            created_at="2026-08-13T05:00:00Z",
            body=f"Show HN: older ship\n\n{SHIP_PR}",
        )
        newer = _put_draft(
            self.repo,
            project_id="app-1",
            brief_id="newer",
            created_at="2026-08-13T06:00:00Z",
            body=f"Show HN: newer ship\n\n{SHIP_PR}",
        )
        out = emit_angle(self.repo)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["draft_id"], newer.draft_id)
        self.assertEqual(out["brief_id"], "newer")
        self.assertIn("newer ship", out["body"])
        self.assertNotIn("older ship", out["body"])
        self.assertNotIsInstance(out.get("drafts"), list)
        self.assertEqual(len(self.repo.list_operator_drafts("app-1")), 2)

    def test_secret_body_is_not_wearable_so_outbox_is_silence(self) -> None:
        leak = "env:INFLUENZER_TOKEN"
        self.assertFalse(
            is_wearable(
                Draft(
                    project_id="app-1",
                    brief_id="secret",
                    draft_id="draft-secret",
                    arena=ArenaId.HN,
                    costume="seminar",
                    angle="one",
                    body=f"Show HN: docs mention {leak}\n\n{SHIP_PR}",
                    wave_checklist=(),
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                    created_at="2026-08-13T05:00:00Z",
                )
            )
        )
        _put_draft(
            self.repo,
            project_id="app-1",
            brief_id="secret",
            created_at="2026-08-13T07:00:00Z",
            body=f"Show HN: docs mention {leak}\n\n{SHIP_PR}",
        )
        out = emit_angle(self.repo, project_id="app-1")
        self.assertEqual(out["status"], "noop")
        self.assertTrue(out["empty"])
        self.assertEqual(out["reason"], "no_draft")
        self.assertIsNone(out["body"])
        self.assertFalse(out["published"])
        self.assertNotIn(leak, str(out))

    def test_dump_body_is_not_wearable_so_silence_or_skip(self) -> None:
        self.assertFalse(
            is_wearable(
                Draft(
                    project_id="app-1",
                    brief_id="dump",
                    draft_id="draft-dump",
                    arena=ArenaId.HN,
                    costume="seminar",
                    angle="one",
                    body="Costume: seminar\nOne arena: hn\nOne angle: dump",
                    wave_checklist=(),
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                    created_at="2026-08-13T05:00:00Z",
                )
            )
        )
        _put_draft(
            self.repo,
            project_id="app-1",
            brief_id="dump",
            created_at="2026-08-13T07:00:00Z",
            body="Costume: seminar\nOne arena: hn",
        )
        wearable = _put_draft(
            self.repo,
            project_id="app-1",
            brief_id="wear",
            created_at="2026-08-13T05:00:00Z",
            body=f"Show HN: wearable\n\n{SHIP_PR}",
        )
        out = emit_angle(self.repo)
        self.assertEqual(out["draft_id"], wearable.draft_id)
        self.assertNotIn("Costume:", out["body"])

    def test_cli_angle_and_module_main_are_read_only_and_offline(self) -> None:
        _put_draft(
            self.repo,
            project_id="app-1",
            brief_id="b-ship",
            created_at="2026-08-13T05:00:00Z",
            body=f"Show HN: Local tick scores briefs\n\n{SHIP_PR}",
        )
        before = self._snapshot_drafts()
        buf = io.StringIO()
        with (
            patch("subprocess.run", side_effect=AssertionError("outbox must not call subprocess")),
            patch("urllib.request.urlopen", side_effect=AssertionError("outbox must not fetch")),
            redirect_stdout(buf),
        ):
            code = cli_main(["--config", str(self.home / "config.json"), "angle"])
        self.assertEqual(code, 0)
        printed = json.loads(buf.getvalue())
        self.assertEqual(printed["status"], "ok")
        self.assertTrue(printed["body"].startswith("Show HN:"))
        self.assertFalse(printed["published"])

        empty_home = self.home / "empty"
        empty_cfg = Config(home=empty_home, scheduler_live_enabled=False)
        write_config(empty_home / "config.json", empty_cfg)
        module_buf = io.StringIO()
        with (
            patch("subprocess.run", side_effect=AssertionError("outbox must not call subprocess")),
            redirect_stdout(module_buf),
        ):
            code = outbox_main(["--config", str(empty_home / "config.json")])
        self.assertEqual(code, 0)
        silenced = json.loads(module_buf.getvalue())
        self.assertEqual(silenced["status"], "noop")
        self.assertTrue(silenced["empty"])
        self.assertEqual(silenced["reason"], "no_draft")
        self.assertEqual(self._snapshot_drafts(), before)
        self.assertFalse((self.home / "runtime.db").exists())
        self.assertFalse((empty_home / "runtime.db").exists())
        self.assertFalse(json.loads((self.home / "config.json").read_text(encoding="utf-8"))["scheduler"]["live_enabled"])

    def test_fala_result_does_not_open_runtime_db(self) -> None:
        from influenzer.fala_result import write_fala_result

        fala_out = self.home / "fala-out"
        payload = emit_angle(self.repo)
        path = write_fala_result(payload, env={"FALA_EFFECTOR_OUTPUT_DIR": str(fala_out)}, reaction_kind="hom.angle")
        assert path is not None
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["reactions"][0]["kind"], "hom.angle")
        self.assertFalse(data["metadata"]["published"])
        self.assertFalse(data["metadata"]["mutated"])
        self.assertFalse((self.home / "runtime.db").exists())


class HomOutboxBlockBoundaryTests(unittest.TestCase):
    def test_module_lists_what_it_refuses(self) -> None:
        src = Path(__file__).resolve().parents[1] / "influenzer" / "hom_outbox.py"
        blob = src.read_text(encoding="utf-8")
        self.assertIn("Does not survey GitHub", blob)
        self.assertIn("Does not call gh", blob)
        self.assertIn("Does not score", blob)
        self.assertIn("Does not dress", blob)
        self.assertIn("Does not publish", blob)
        self.assertIn("Does not enable live social", blob)
        self.assertIn("Does not know Heimdall", blob)
        self.assertIn("Does not send mail", blob)
        self.assertIn("Does not write state.db", blob)
        self.assertIn("Does not open runtime.db", blob)
        imports = _import_lines(src)
        self.assertFalse(any("github_survey" in line or "github_pack" in line for line in imports))
        self.assertFalse(any("hom_draft" in line for line in imports))
        self.assertFalse(any("scheduler" in line or "tick_all" in line for line in imports))
        self.assertFalse(any("subprocess" in line for line in imports))
        self.assertFalse(any("webbrowser" in line for line in imports))
        init = (Path(__file__).resolve().parents[1] / "influenzer" / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("hom_outbox", init)
        hom = (Path(__file__).resolve().parents[1] / "influenzer" / "hom.py").read_text(encoding="utf-8")
        self.assertNotIn("hom_outbox", hom)
        draft = (Path(__file__).resolve().parents[1] / "influenzer" / "hom_draft.py").read_text(encoding="utf-8")
        self.assertNotIn("hom_outbox", draft)

    def test_fala_package_lists_outbox_organ(self) -> None:
        root = Path(__file__).resolve().parents[1]
        package = tomllib.loads((root / "fala-package.toml").read_text(encoding="utf-8"))
        caps = {item["id"] for item in package["capabilities"]}
        self.assertIn("hom_outbox", caps)
        paths = {item["id"]: item for item in package["correlation_paths"]}
        self.assertIn("hom_outbox", paths)
        commands = [item["adapter"]["command"] for item in paths["hom_outbox"]["effectors"]]
        self.assertEqual(commands, [["python3", "-m", "influenzer.hom_outbox"]])
        self.assertEqual(len(paths["operator_tick"]["effectors"]), 1)
        self.assertEqual(len(paths["hom_draft"]["effectors"]), 1)
        blob = json.dumps(package)
        self.assertNotIn("native_function", blob)
        self.assertNotIn("ads", blob.lower())
        self.assertIn("Does not survey GitHub", paths["hom_outbox"]["description"])
        self.assertIn("Does not", paths["hom_outbox"]["description"])


if __name__ == "__main__":
    unittest.main()
