"""Evaluate retrieved evidence and preserve per-query traces."""
from __future__ import annotations

import re
from typing import Any


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _is_hit(question: dict[str, Any], hit: dict[str, Any]) -> bool:
    """A hit is valid if source_id & page match gold and the chunk contains the gold evidence."""
    gold_source = question["gold_source_id"]
    gold_pages = question["gold_page"]
    if not isinstance(gold_pages, list):
        gold_pages = [gold_pages]

    if hit.get("document_id") != gold_source or hit.get("page") not in gold_pages:
        return False

    hit_norm = _collapse_ws(hit.get("text", ""))
    evidences = question["evidence_quote"]
    if not isinstance(evidences, list):
        evidences = [evidences]

    return any(_collapse_ws(ev) in hit_norm for ev in evidences)


def _filter_compliant(question: dict[str, Any], hits: list[dict[str, Any]]) -> bool | None:
    flt = question.get("filter")
    if not flt:
        return None
    for hit in hits:
        for k, v in flt.items():
            if hit.get(k) != v and hit.get("metadata", {}).get(k) != v:
                return False
    return True


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Check source/page and gold evidence; return full top-k trace."""
    annotated_hits = []
    for rank, hit in enumerate(hits, start=1):
        annotated_hits.append({**hit, "rank": rank, "is_hit": _is_hit(question, hit)})

    hit_at_1 = bool(annotated_hits and annotated_hits[0]["is_hit"])
    hit_at_3 = any(h["is_hit"] for h in annotated_hits[:3])

    return {
        "question_id": question["id"],
        "split": question["split"],
        "type": question.get("type", ""),
        "question": question["question"],
        "gold_source_id": question["gold_source_id"],
        "gold_page": question["gold_page"],
        "filter": question.get("filter"),
        "filter_compliant": _filter_compliant(question, annotated_hits),
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "hits": annotated_hits,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate Hit@1, Evidence Hit@3, and filter compliance by strategy and split."""
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for t in traces:
        grouped.setdefault((t["strategy"], t["split"]), []).append(t)

    summary: dict[str, dict[str, Any]] = {}
    for (strategy, split), items in sorted(grouped.items()):
        total = len(items)
        h1 = sum(1 for x in items if x["hit_at_1"])
        h3 = sum(1 for x in items if x["hit_at_3"])
        filtered = [x for x in items if x["filter"] is not None]
        flt_ok = sum(1 for x in filtered if x["filter_compliant"])
        summary.setdefault(strategy, {})[split] = {
            "total": total,
            "hit_at_1_count": h1,
            "hit_at_1_rate": round(h1 / total, 4) if total else 0.0,
            "hit_at_3_count": h3,
            "hit_at_3_rate": round(h3 / total, 4) if total else 0.0,
            "filtered_total": len(filtered),
            "filter_compliant_count": flt_ok,
        }
    return summary
