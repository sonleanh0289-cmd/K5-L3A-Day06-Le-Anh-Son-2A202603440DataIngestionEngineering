"""Local BAAI/bge-m3 embedding adapter using SentenceTransformers."""
from __future__ import annotations

import os
from typing import Protocol


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """Real local embedding provider backed by SentenceTransformers (BAAI/bge-m3)."""

    def __init__(self, model_name: str = "BAAI/bge-m3", local_files_only: bool = True) -> None:
        self.model_name = model_name
        if local_files_only:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name, local_files_only=local_files_only)
        get_dim = getattr(self._model, "get_embedding_dimension", self._model.get_sentence_embedding_dimension)
        dim = get_dim()
        if dim is None:
            raise RuntimeError(f"Could not determine embedding dimension for {model_name}")
        self.dimensions = int(dim)

    def embed_documents(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vec.tolist() for vec in vectors]

    def embed_query(self, question: str) -> list[float]:
        vector = self._model.encode(
            [question],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]
        return vector.tolist()
