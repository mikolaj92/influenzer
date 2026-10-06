import unittest

from influenzer.model_review import evidence_fragments


class FragmentTests(unittest.TestCase):
    def test_fragment_ids_bind_exact_source_not_model_retyped_text(self):
        evidence = [{"evidence_id": "x:1", "content": "You could use local AI.\nPrivate &amp; offline PDFs?"}]
        fragments = evidence_fragments(evidence)
        self.assertEqual("".join(f["text"] for f in fragments), evidence[0]["content"])
        self.assertEqual(fragments, evidence_fragments(evidence))
        self.assertTrue(all(len(f["fragment_id"]) <= 14 for f in fragments))
        self.assertTrue(all(len(f["span_digest"]) == 64 for f in fragments))
        self.assertEqual({f["evidence_id"] for f in fragments}, {"x:1"})
        changed = evidence_fragments([{**evidence[0], "content": "you could use local AI."}])
        self.assertNotEqual(fragments[0]["fragment_id"], changed[0]["fragment_id"])

    def test_fragment_ids_do_not_depend_on_feed_order(self):
        first = {"evidence_id": "x:1", "content": "You need offline AI?"}
        other = {"evidence_id": "x:2", "content": "Other source."}
        self.assertEqual(evidence_fragments([first])[0], evidence_fragments([other, first])[1])

    def test_collision_is_named_not_silently_resolved(self):
        from unittest.mock import patch
        with patch("influenzer.model_review.content_hash", return_value="a" * 64), self.assertRaisesRegex(ValueError, "fragment_id_collision"):
            evidence_fragments([{"evidence_id": "1", "content": "A"}, {"evidence_id": "2", "content": "B"}])

    def test_long_posts_are_losslessly_bounded_fragments_without_semantic_filter(self):
        evidence = [{"evidence_id": "x:1", "content": "x" * 1800 + " &amp; " + "?" * 50}]
        fragments = evidence_fragments(evidence)
        self.assertEqual("".join(f["text"] for f in fragments), evidence[0]["content"])
        self.assertTrue(all(0 < len(f["text"]) <= 800 for f in fragments))
        for f in fragments:
            self.assertEqual(evidence[0]["content"][f["start"]:f["end"]], f["text"])
