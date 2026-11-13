"""PostgreSQL + pgvector store with idempotent upsert and parameterized metadata filtering."""
from __future__ import annotations

import json
from typing import Any

import psycopg

from .models import Chunk

_ALLOWED_FILTERS = {"chapter", "document_id", "page", "language", "year"}


def _to_pgvector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if not database_url:
            raise ValueError("DATABASE_URL is required")
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.database_url = database_url
        self.dimensions = int(dimensions)

    def create_schema(self) -> None:
        """Create vector table and metadata indexes if they do not exist."""
        ddl = f"""
        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE TABLE IF NOT EXISTS day6_chunks (
            id SERIAL PRIMARY KEY,
            strategy TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            source TEXT NOT NULL,
            page INTEGER NOT NULL,
            chapter TEXT,
            text TEXT NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            embedding vector({self.dimensions}) NOT NULL,
            UNIQUE (strategy, chunk_id)
        );
        CREATE INDEX IF NOT EXISTS idx_day6_chunks_strategy ON day6_chunks (strategy);
        CREATE INDEX IF NOT EXISTS idx_day6_chunks_chapter ON day6_chunks (strategy, chapter);
        """
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()

    def count_chunks(self, strategy: str) -> int:
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM day6_chunks WHERE strategy = %s", (strategy,))
                row = cur.fetchone()
                return int(row[0]) if row else 0

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Validate lengths/dimensions, remove stale chunks for re-ingested docs, and upsert."""
        if len(chunks) != len(vectors):
            raise ValueError(f"Mismatch: {len(chunks)} chunks vs {len(vectors)} vectors")
        if not chunks:
            return

        for i, vec in enumerate(vectors):
            if len(vec) != self.dimensions:
                raise ValueError(f"Vector {i} has dim {len(vec)}, expected {self.dimensions}")

        doc_ids = sorted({c.document_id for c in chunks})
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                for doc_id in doc_ids:
                    active_ids = [c.chunk_id for c in chunks if c.document_id == doc_id]
                    cur.execute(
                        """
                        DELETE FROM day6_chunks
                        WHERE strategy = %s AND document_id = %s AND NOT (chunk_id = ANY(%s))
                        """,
                        (strategy, doc_id, active_ids),
                    )

                sql = """
                INSERT INTO day6_chunks (strategy, chunk_id, document_id, source, page, chapter, text, metadata, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::vector)
                ON CONFLICT (strategy, chunk_id) DO UPDATE SET
                    document_id = EXCLUDED.document_id,
                    source = EXCLUDED.source,
                    page = EXCLUDED.page,
                    chapter = EXCLUDED.chapter,
                    text = EXCLUDED.text,
                    metadata = EXCLUDED.metadata,
                    embedding = EXCLUDED.embedding
                """
                rows = [
                    (
                        strategy,
                        c.chunk_id,
                        c.document_id,
                        c.source,
                        c.page,
                        c.metadata.get("chapter"),
                        c.text,
                        json.dumps(c.metadata, ensure_ascii=False),
                        _to_pgvector_literal(vec),
                    )
                    for c, vec in zip(chunks, vectors)
                ]
                cur.executemany(sql, rows)
            conn.commit()

    def search(
        self,
        strategy: str,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Filter permitted metadata in SQL, rank by cosine distance, and return top-k."""
        if len(query_vector) != self.dimensions:
            raise ValueError(f"Query vector dim {len(query_vector)} != {self.dimensions}")

        where_clauses = ["strategy = %s"]
        q_lit = _to_pgvector_literal(query_vector)
        filter_params: list[Any] = [strategy]

        if filters:
            for key, val in filters.items():
                if key not in _ALLOWED_FILTERS:
                    raise ValueError(f"Unsupported filter field: {key}")
                if key in {"chapter", "document_id", "page"}:
                    where_clauses.append(f"{key} = %s")
                    filter_params.append(val)
                else:
                    where_clauses.append("metadata ->> %s = %s")
                    filter_params.extend([key, str(val)])

        sql = f"""
        SELECT
            chunk_id,
            document_id,
            source,
            page,
            chapter,
            text,
            metadata,
            1 - (embedding <=> %s::vector) AS cosine_similarity
        FROM day6_chunks
        WHERE {' AND '.join(where_clauses)}
        ORDER BY embedding <=> %s::vector ASC
        LIMIT %s
        """
        params = [q_lit, *filter_params, q_lit, top_k]

        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        return [
            {
                "chunk_id": r[0],
                "document_id": r[1],
                "source": r[2],
                "page": int(r[3]),
                "chapter": r[4],
                "text": r[5],
                "metadata": r[6] if isinstance(r[6], dict) else json.loads(r[6]),
                "score": round(float(r[7]), 6),
            }
            for r in rows
        ]
