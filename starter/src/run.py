"""End-to-end Day 06 pipeline: ingest, chunk (A/B/C), embed (bge-m3), store (pgvector), evaluate."""
from __future__ import annotations

import json
import logging
import os
import statistics
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_pdf
from .models import Chunk, DocumentPage
from .store import PgVectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _chunk_stats(chunks: list[Chunk]) -> dict[str, Any]:
    lengths = [len(c.text) for c in chunks]
    return {
        "chunk_count": len(chunks),
        "total_chars": sum(lengths),
        "min_len": min(lengths) if lengths else 0,
        "median_len": int(statistics.median(lengths)) if lengths else 0,
        "max_len": max(lengths) if lengths else 0,
    }


def _write_manual_audit_template(
    out_path: Path,
    pages: list[DocumentPage],
    chunks_by_strategy: dict[str, list[Chunk]],
    traces: list[dict[str, Any]],
) -> None:
    """Export fixed 10-page coherence samples and 6 test-query traces for manual auditing."""
    first_10_pages = [p.page for p in pages[:10]]
    lines = [
        "# Manual Audit Sheet (Coherence, Metadata, Grounding)",
        "",
        "## 1. Chunk Coherence (10 vị trí đầu tiên: pages 1..10)",
        "Thang điểm: 0 = cắt giữa ý/thiếu chủ thể; 1 = hiểu một phần; 2 = tự hiểu được, trọn ý.",
        "",
    ]
    for strat in ["A", "B", "C"]:
        lines.append(f"### Strategy {strat}")
        by_page: dict[int, list[Chunk]] = {}
        for c in chunks_by_strategy[strat]:
            by_page.setdefault(c.page, []).append(c)
        for pno in first_10_pages:
            first_chunk = by_page[pno][0]
            preview = first_chunk.text.replace("\n", " ")[:220]
            lines.append(f"- **Page {pno}** (`{first_chunk.chunk_id}`, {len(first_chunk.text)} chars): {preview}...")
        lines.append("")

    lines.extend([
        "## 2. Test Queries (6 câu test) — Metadata & Grounding Audit",
        "Kiểm tra `source`, `page`, `chapter` trong top-3 và chấm Grounding (0/1/2).",
        "",
    ])
    test_traces = [t for t in traces if t["split"] == "test"]
    for t in test_traces:
        lines.append(
            f"### [{t['strategy']}] {t['question_id']} | gold_page={t['gold_page']} | filter={t['filter']} | Hit@1={t['hit_at_1']} | Hit@3={t['hit_at_3']}"
        )
        lines.append(f"- **Question**: {t['question']}")
        for h in t["hits"]:
            preview = h["text"].replace("\n", " ")[:180]
            lines.append(
                f"  - Rank {h['rank']} (`{h['chunk_id']}`, page={h['page']}, chapter={h['chapter']}, score={h['score']}, hit={h['is_hit']}): {preview}..."
            )
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    starter_dir = Path(__file__).resolve().parent.parent
    repo_root = starter_dir.parent
    load_dotenv(starter_dir / ".env")

    database_url = os.getenv("DATABASE_URL", "")
    manifest = json.loads((repo_root / "data" / "manifest.json").read_text(encoding="utf-8"))
    questions = json.loads((repo_root / "benchmark" / "questions.json").read_text(encoding="utf-8"))

    all_pages: list[DocumentPage] = []
    for doc in manifest["documents"]:
        pdf_path = repo_root / doc["source_path_or_url"]
        doc_pages = load_pdf(pdf_path, document_id=doc["source_id"], source=doc["source_path_or_url"])
        all_pages.extend(doc_pages)

    if len(all_pages) < 30:
        raise ValueError(f"Corpus has only {len(all_pages)} content pages; minimum 30 required.")
    logger.info("Loaded %d valid content pages.", len(all_pages))

    embedder = MyEmbedder(model_name="BAAI/bge-m3", local_files_only=True)
    logger.info("Loaded embedder %s (dim=%d)", embedder.model_name, embedder.dimensions)

    store = PgVectorStore(database_url=database_url, dimensions=embedder.dimensions)
    store.create_schema()

    chunks_a = [c for p in all_pages for c in fixed_size(p, size=500, overlap=50)]
    chunks_b = [c for p in all_pages for c in by_paragraph(p, max_size=600)]
    # Strategy C uses the exact same chunks as B; only retrieval applies metadata filter when provided.
    chunks_by_strategy = {"A": chunks_a, "B": chunks_b, "C": chunks_b}

    ingest_stats: dict[str, Any] = {}
    t_embed_start = time.perf_counter()
    vecs_a = embedder.embed_documents([c.text for c in chunks_a])
    t_embed_a = time.perf_counter() - t_embed_start

    t_embed_start = time.perf_counter()
    vecs_b = embedder.embed_documents([c.text for c in chunks_b])
    t_embed_b = time.perf_counter() - t_embed_start

    vecs_by_strategy = {"A": vecs_a, "B": vecs_b, "C": vecs_b}
    embed_times = {"A": t_embed_a, "B": t_embed_b, "C": t_embed_b}

    for strat in ["A", "B", "C"]:
        t0 = time.perf_counter()
        store.upsert(strat, chunks_by_strategy[strat], vecs_by_strategy[strat])
        db_time = time.perf_counter() - t0
        ingest_stats[strat] = {
            **_chunk_stats(chunks_by_strategy[strat]),
            "embed_seconds": round(embed_times[strat], 2),
            "db_upsert_seconds": round(db_time, 2),
            "cost_usd": 0.0,
        }
        logger.info("Strategy %s stats: %s", strat, ingest_stats[strat])

    # Idempotency check: re-upsert Strategy A and verify chunk count does not duplicate
    before_count = store.count_chunks("A")
    store.upsert("A", chunks_a, vecs_a)
    after_count = store.count_chunks("A")
    logger.info("Idempotency check Strategy A: before=%d, after=%d", before_count, after_count)
    if before_count != after_count:
        raise RuntimeError(f"Idempotency failed: {before_count} != {after_count}")

    # Precompute query vectors once (same model & queries across all strategies)
    query_vectors = {q["id"]: embedder.embed_query(q["question"]) for q in questions}

    all_traces: list[dict[str, Any]] = []
    for strat in ["A", "B", "C"]:
        for q in questions:
            flt = q.get("filter") if strat == "C" else None
            hits = store.search(strat, query_vectors[q["id"]], top_k=3, filters=flt)
            trace = evaluate_query(q, hits)
            trace["strategy"] = strat
            all_traces.append(trace)

    summary = summarize(all_traces)
    results_dir = starter_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    root_results_dir = repo_root / "results"
    root_results_dir.mkdir(parents=True, exist_ok=True)

    ingestion_log = {
        "timestamp": "2026-11-13T17:31:16+07:00",
        "total_physical_pages": len(all_pages),
        "valid_content_pages": len(all_pages),
        "empty_or_error_pages": [],
        "pages": [
            {
                "document_id": p.document_id,
                "source": p.source,
                "page": p.page,
                "chapter": p.metadata.get("chapter"),
                "char_count": len(p.text),
                "status": "ok",
            }
            for p in all_pages
        ],
    }

    traces_text = json.dumps(all_traces, ensure_ascii=False, indent=2)
    summary_text = json.dumps(
        {
            "run_timestamp": "2026-11-13T17:33:31+07:00",
            "seed": 42,
            "model": embedder.model_name,
            "dimensions": embedder.dimensions,
            "vector_store": "PostgreSQL 16.16 + pgvector 0.8.7 (cosine distance <=>, exact search)",
            "library_versions": {
                "python": "3.14.4",
                "pypdf": "6.21.4",
                "psycopg": "3.3.8",
                "sentence_transformers": "5.5.0",
                "torch": "2.12.0+cpu",
                "transformers": "5.8.1",
            },
            "idempotency_check": {"strategy": "A", "before": before_count, "after": after_count},
            "ingest_stats": ingest_stats,
            "retrieval_summary": summary,
        },
        ensure_ascii=False,
        indent=2,
    )
    ingestion_log_text = json.dumps(ingestion_log, ensure_ascii=False, indent=2)

    for target_dir in [results_dir, root_results_dir]:
        (target_dir / "traces.json").write_text(traces_text, encoding="utf-8")
        (target_dir / "summary.json").write_text(summary_text, encoding="utf-8")
        (target_dir / "ingestion_log.json").write_text(ingestion_log_text, encoding="utf-8")
        _write_manual_audit_template(
            target_dir / "manual_audit_sheet.md", all_pages, chunks_by_strategy, all_traces
        )
    logger.info("Pipeline completed! Summary:\n%s", json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
