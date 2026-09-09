"""Shared numbers for the pgvector layer.

Read this file first if you wonder "why 2048?" or "what gets embedded?".
"""

# Width of every vector in `code_embeddings.embedding`.
# Must match tables.py + migration 0003. GLM embedding-3 uses 2048.
# If you switch models, add a new migration — never truncate silently.
EMBEDDING_DIMENSIONS = 2048

# How many texts we pass to ModelAdapter.embed() per call during indexing.
EMBED_BATCH_SIZE = 32

# How many embedding rows we bind per INSERT/UPSERT execute.
WRITE_BATCH_SIZE = 500

# Tree-sitter symbol kinds that become one chunk each.
# module = whole file header only → skip (too vague).
# import = just an import line → skip (not useful for semantic search).
CHUNK_KINDS = frozenset({"class", "function", "method"})

# Hard cap on text sent to ModelAdapter.embed(). ~6k–8k tokens at ~4 chars/token.
# Robustness only — not a retrieval-quality knob.
MAX_CHUNK_CHARS = 24 * 1024

# Rough token budget for Section 06 context packing. Not billed usage.
CHARS_PER_TOKEN = 4

# Fetch extra cosine neighbors so overlapping-span collapse can still fill top_k.
SEARCH_OVERFETCH = 4
