"""
app/services/rag.py
===================
Knowledge & RAG (Retrieval-Augmented Generation) Service.

Responsibility:
  Index organizational knowledge (glossaries, templates, domain policies,
  past BRDs) into a local ChromaDB vector store and retrieve relevant
  context fragments during AI capability execution.

Design:
  - Uses ChromaDB with a local `SentenceTransformerEmbeddingFunction` so
    no external embedding API is needed. The model (`all-MiniLM-L6-v2`)
    runs locally and produces 384-dimensional vectors.
  - The collection is persisted to disk (CHROMA_DB_PATH from settings) so
    indexed documents survive server restarts.
  - `search_context` returns the top-k most semantically similar chunks.

Failure behaviour (PDS Chapter 14 - RAG miss handling):
  - If ChromaDB is unreachable or returns no results, search_context
    returns an empty string and logs a warning.
  - The caller (PromptOrchestrator) proceeds with an empty RAG context
    rather than failing the pipeline.
"""

from __future__ import annotations

import logging
from typing import Any

try:
    import chromadb
    from chromadb.utils import embedding_functions
    HAVE_CHROMADB = True
except ImportError:
    HAVE_CHROMADB = False
    chromadb = None
    embedding_functions = None

from app.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "area_knowledge_base"


class RAGService:
    """
    Manages the ChromaDB vector store for organizational knowledge retrieval.

    Usage:
        rag = RAGService()
        context = rag.search_context("guest checkout policy", n_results=3)
        rag.index_document("glossary_v1", "Guest checkout allows ...", {"source": "glossary"})
    """

    def __init__(self) -> None:
        if not HAVE_CHROMADB:
            logger.warning("ChromaDB is not installed. RAG service running in graceful degradation mode.")
            self._collection = None
            return

        try:
            self._client = chromadb.PersistentClient(path=settings.CHROMA_DB_PATH)
            self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=settings.EMBEDDING_MODEL
            )
            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=self._embedding_fn,
                metadata={"hnsw:space": "cosine"},  # Cosine similarity for semantic search
            )
            logger.info(
                f"RAG service initialised. Collection '{COLLECTION_NAME}' "
                f"has {self._collection.count()} documents."
            )
        except Exception as exc:
            logger.error(f"RAG service failed to initialise: {exc}")
            self._collection = None  # Graceful degradation


    # ------------------------------------------------------------------ #
    # Indexing
    # ------------------------------------------------------------------ #

    def index_document(
        self,
        doc_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Add or update a document in the vector store.

        Args:
            doc_id:   Unique identifier for the document (used for upserts).
            content:  Plain text to embed and store.
            metadata: Optional key-value metadata (e.g. {"source": "company_brd_v1"}).

        Returns:
            True on success, False on failure.
        """
        if self._collection is None:
            logger.warning("RAG service unavailable. Skipping document indexing.")
            return False

        try:
            self._collection.upsert(
                ids=[doc_id],
                documents=[content],
                metadatas=[metadata or {}],
            )
            logger.debug(f"RAG: indexed document '{doc_id}'")
            return True
        except Exception as exc:
            logger.error(f"RAG indexing failed for '{doc_id}': {exc}")
            return False

    def index_documents_batch(self, documents: list[dict[str, Any]]) -> int:
        """
        Batch-index a list of documents.

        Each dict must have: id (str), content (str), metadata (dict, optional).
        Returns the count of successfully indexed documents.
        """
        if self._collection is None:
            return 0

        ids, contents, metadatas = [], [], []
        for doc in documents:
            ids.append(doc["id"])
            contents.append(doc["content"])
            metadatas.append(doc.get("metadata", {}))

        try:
            self._collection.upsert(ids=ids, documents=contents, metadatas=metadatas)
            logger.info(f"RAG: batch-indexed {len(ids)} documents.")
            return len(ids)
        except Exception as exc:
            logger.error(f"RAG batch indexing failed: {exc}")
            return 0

    # ------------------------------------------------------------------ #
    # Retrieval
    # ------------------------------------------------------------------ #

    def search_context(
        self,
        query: str,
        n_results: int = 3,
        where_filter: dict[str, Any] | None = None,
        max_distance: float | None = None,
    ) -> str:
        """
        Retrieve the top-k most semantically similar knowledge fragments.

        Args:
            query:        Free-text query (e.g. a feature description or business rule).
            n_results:    Maximum number of fragments to return.
            where_filter: Optional metadata filtering dictionary (e.g. {"project_id": "proj-123"}).
            max_distance: Optional maximum distance threshold (cosine distance); items above are excluded.

        Returns:
            A single string containing all retrieved fragments joined by
            double newlines. Returns an empty string if the collection is
            unavailable or no results are found.
        """
        if self._collection is None:
            logger.warning("RAG service unavailable. Returning empty context.")
            return ""

        try:
            count = self._collection.count()
            if count == 0:
                logger.debug("RAG collection is empty. No context retrieved.")
                return ""

            # Clamp n_results to available documents
            actual_n = min(n_results, count)
            query_kwargs: dict[str, Any] = {
                "query_texts": [query],
                "n_results": actual_n,
                "include": ["documents", "metadatas", "distances"],
            }
            if where_filter:
                query_kwargs["where"] = where_filter

            results = self._collection.query(**query_kwargs)

            fragments = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]

            if not fragments:
                logger.debug(f"RAG: no results found for query: '{query[:80]}'")
                return ""

            # Filter by max_distance if specified
            filtered_fragments = []
            for i, frag in enumerate(fragments):
                if max_distance is not None and i < len(distances) and distances[i] > max_distance:
                    continue
                filtered_fragments.append(frag)

            if not filtered_fragments:
                logger.debug(f"RAG: all results exceeded max_distance={max_distance} for query: '{query[:80]}'")
                return ""

            logger.debug(f"RAG: retrieved {len(filtered_fragments)} fragments for '{query[:80]}'")
            return "\n\n".join(filtered_fragments)

        except Exception as exc:
            # Non-fatal: log warning and return empty string (PDS degraded mode)
            logger.warning(f"RAG search failed (will continue without context): {exc}")
            return ""

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #

    def count(self) -> int:
        """Return the number of documents currently in the collection."""
        if self._collection is None:
            return 0
        try:
            return self._collection.count()
        except Exception:
            return 0
