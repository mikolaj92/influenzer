"""Transparent comparison against explicit reviewer labels, not model self-scoring."""
import re

from influenzer.model_review import NEED_CATEGORIES


def lexical_category(text: str) -> str | None:
    """Legacy heuristic, evaluation only; never selects production evidence/actions."""
    if "?" in text or re.search(r"\b(how do|how can|anyone know|jak)\b", text, re.IGNORECASE):
        return "question"
    if re.search(r"\b(need|wish|looking for|potrzebuj\w*)\b", text, re.IGNORECASE):
        return "request"
    if re.search(r"\b(broken|fails|doesn't work|cannot|can't|problem|error)\b", text, re.IGNORECASE):
        return "problem"
    return None


def measure(cases: list[dict], proposal: dict) -> dict:
    if not cases or len({c["evidence_id"] for c in cases}) != len(cases):
        raise ValueError("unique labelled cases required")
    predictions = {item["evidence_id"]: item["category"] in NEED_CATEGORIES for item in proposal["interpretations"]}
    if any(c["evidence_id"] not in predictions or type(c["is_need"]) is not bool or type(c["heuristic_need"]) is not bool for c in cases):
        raise ValueError("complete boolean labels and model predictions required")
    scores = {}
    for name in ("heuristic", "model"):
        counts: dict[str, int] = dict.fromkeys(("tp", "fp", "fn", "tn"), 0)
        for case in cases:
            predicted = case["heuristic_need"] if name == "heuristic" else predictions[case["evidence_id"]]
            counts[("t" if predicted == case["is_need"] else "f") + ("p" if predicted else "n")] += 1
        scores[name] = counts
    return {"n": len(cases), **scores,
            "total_tokens": sum((a.get("usage") or {}).get("total_tokens", 0) for a in proposal["audits"]),
            "latency_ms": sum(a.get("latency_ms", 0) for a in proposal["audits"]), "cost": None,
            "decision_usefulness": "requires operator verdict", "scope": "bounded non-random sample; no generalization"}
