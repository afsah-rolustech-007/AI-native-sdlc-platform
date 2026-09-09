"""Semantic embeddings (L3): chunks → ModelAdapter.embed() → pgvector.

Start with pgvector_client.PgvectorClient for index + search.
Chunk building lives in vector/chunks.py; SQL helpers in vector/store.py.
"""
