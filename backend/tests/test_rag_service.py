"""
tests/test_rag_service.py
==========================
Comprehensive Unit Tests for RAGService (ChromaDB + Local SentenceTransformers).

Verifies:
1. RAG initialization and collection creation.
2. Document indexing (single & batch) and semantic similarity retrieval.
3. Disk persistence under CHROMA_DB_PATH and reload across service instances.
4. Distance thresholding and irrelevant query handling.
5. Project/metadata isolation using where_filter.
"""

import os
import shutil
import tempfile
import pytest
from app.services.rag import RAGService


@pytest.fixture
def temp_chroma_dir():
    """Create a temporary directory for isolated ChromaDB tests."""
    temp_dir = tempfile.mkdtemp(prefix="chroma_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_rag_initialization_and_collection(temp_chroma_dir, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "CHROMA_DB_PATH", temp_chroma_dir)

    rag = RAGService()
    assert rag._collection is not None
    assert rag.count() == 0


def test_rag_document_indexing_and_search(temp_chroma_dir, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "CHROMA_DB_PATH", temp_chroma_dir)

    rag = RAGService()
    
    # Single doc indexing
    success = rag.index_document(
        doc_id="policy_001",
        content="Guest users may place orders up to $500 without full account registration.",
        metadata={"source": "guest_policy", "project_id": "proj-alpha"}
    )
    assert success is True
    assert rag.count() == 1

    # Batch doc indexing
    batch = [
        {
            "id": "policy_002",
            "content": "Registered corporate accounts receive 30-day invoice payment terms.",
            "metadata": {"source": "corporate_policy", "project_id": "proj-alpha"}
        },
        {
            "id": "policy_003",
            "content": "All refunds are credited to the original payment method within 5 business days.",
            "metadata": {"source": "refund_policy", "project_id": "proj-beta"}
        }
    ]
    indexed_count = rag.index_documents_batch(batch)
    assert indexed_count == 2
    assert rag.count() == 3

    # Semantic retrieval search
    context = rag.search_context("How do refunds work for customers?", n_results=1)
    assert "refunds are credited to the original payment method" in context


def test_rag_persistence_and_reload(temp_chroma_dir, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "CHROMA_DB_PATH", temp_chroma_dir)

    # Instance 1: Index document
    rag1 = RAGService()
    rag1.index_document(
        doc_id="persist_001",
        content="System must comply with ISO-27001 data security standards.",
        metadata={"category": "security"}
    )
    assert rag1.count() == 1

    # Instance 2: Reload from disk
    rag2 = RAGService()
    assert rag2.count() == 1
    retrieved = rag2.search_context("security compliance standard", n_results=1)
    assert "ISO-27001" in retrieved


def test_rag_distance_threshold_and_irrelevant_query(temp_chroma_dir, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "CHROMA_DB_PATH", temp_chroma_dir)

    rag = RAGService()
    rag.index_document(
        doc_id="item_01",
        content="Pizza toppings include pepperoni, mushrooms, and mozzarella cheese.",
        metadata={"domain": "food"}
    )

    # Strict distance threshold should filter out highly irrelevant query
    retrieved = rag.search_context("Kubernetes pod scaling architecture", n_results=1, max_distance=0.1)
    assert retrieved == ""


def test_rag_project_isolation_filter(temp_chroma_dir, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "CHROMA_DB_PATH", temp_chroma_dir)

    rag = RAGService()
    rag.index_document("doc_p1", "Project Alpha user authentication design", {"project_id": "proj-A"})
    rag.index_document("doc_p2", "Project Beta payment processing design", {"project_id": "proj-B"})

    # Filter for Project A only
    context_a = rag.search_context("design specification", n_results=2, where_filter={"project_id": "proj-A"})
    assert "Project Alpha" in context_a
    assert "Project Beta" not in context_a

    # Filter for Project B only
    context_b = rag.search_context("design specification", n_results=2, where_filter={"project_id": "proj-B"})
    assert "Project Beta" in context_b
    assert "Project Alpha" not in context_b
