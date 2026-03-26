"""Generator service — thin re-export; generation logic lives in RAGChain."""
# Generation is implemented in app/chains/rag_chain.py (RAGChain.invoke / stream).
# This file exists for import compatibility.
from app.chains.rag_chain import RAGChain as GeneratorService  # noqa: F401
