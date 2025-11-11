"""AI package for embeddings, recommenders and imagery.

This package provides a lightweight, local-first implementation:
- embeddings: TF-IDF fallback or sentence-transformers when available
- vector store: sklearn NearestNeighbors (faiss optional if installed)
- imagery: local placeholder generator (PIL)

Modules exported here are intentionally small and test-friendly; adapters
can be implemented later to call OpenAI / Replicate / Pinecone.
"""
from .embeddings import EmbeddingIndexer  # type: ignore
from .recommender import Recommender  # type: ignore
from .imagery import generate_image  # type: ignore

__all__ = ["EmbeddingIndexer", "Recommender", "generate_image"]
