"""Debug endpoint — inspect FAISS index contents and similarity scores."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.db.document_registry import DocumentRegistry
from app.db.vector_store import VectorStore
from app.dependencies import get_document_registry, get_embedder, get_settings, get_vector_store
from app.services.embedder import EmbedderService

router = APIRouter(tags=["debug"])


@router.get("/debug/index")
async def debug_index(
    vector_store: VectorStore = Depends(get_vector_store),
    registry: DocumentRegistry = Depends(get_document_registry),
):
    """Show FAISS index stats and all stored document IDs."""
    from app.db.faiss_store import FAISSStore
    stats = await vector_store.get_collection_stats()
    all_docs = await registry.get_all()

    stored_doc_ids: list[str] = []
    if isinstance(vector_store, FAISSStore):
        stored_doc_ids = list({
            meta["document_id"]
            for meta in vector_store._metadata.values()
        })

    return {
        "faiss_stats": stats,
        "registry_documents": [
            {"id": d.document_id, "name": d.filename, "status": d.status}
            for d in all_docs
        ],
        "faiss_document_ids": stored_doc_ids,
        "threshold_in_use": None,  # shown in /debug/search
    }


@router.get("/debug/search")
async def debug_search(
    q: str = Query(..., description="Query text to test similarity"),
    doc_id: str = Query(None, description="Filter by document_id (optional)"),
    vector_store: VectorStore = Depends(get_vector_store),
    embedder: EmbedderService = Depends(get_embedder),
    settings=Depends(get_settings),
):
    """Embed a query and show raw similarity scores from FAISS."""
    from app.db.faiss_store import FAISSStore

    embedding = await embedder.embed_query(q)

    doc_ids = [doc_id] if doc_id else None

    # Fetch all candidates (no threshold)
    raw = await vector_store.search(embedding, top_k=20, document_ids=doc_ids)

    results = [
        {
            "score": round(score, 4),
            "document_id": chunk.document_id,
            "document_name": chunk.document_name,
            "chunk_index": chunk.chunk_index,
            "page_numbers": chunk.page_numbers,
            "text_preview": chunk.text[:120].replace("\n", " "),
        }
        for chunk, score in raw
    ]

    return {
        "query": q,
        "threshold_in_config": settings.similarity_threshold,
        "total_vectors_in_index": (await vector_store.get_collection_stats())["total_vectors"],
        "results_found": len(results),
        "results": results,
    }
