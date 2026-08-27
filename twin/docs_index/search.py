"""BM25 search over the committed Beam docs artifact.

The index artifact stores pre-tokenized chunks; BM25Okapi is rebuilt at import
(~100 ms) instead of pickling the model. v2 swaps these internals for a vector
DB / knowledge graph behind the same search() signature.
"""

import gzip
import json
from pathlib import Path

from rank_bm25 import BM25Okapi

from .build_index import tokenize

_ARTIFACT = Path(__file__).parent / "beam_docs_index.json.gz"

with gzip.open(_ARTIFACT, "rt", encoding="utf-8") as _f:
    _payload = json.load(_f)

CHUNKS: list[dict] = _payload["chunks"]
_bm25 = BM25Okapi([c["tokens"] for c in CHUNKS])


def search(query: str, k: int = 5) -> list[dict]:
    """Return the top-k doc chunks as {url, title, heading, text}."""
    scores = _bm25.get_scores(tokenize(query))
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    return [
        {key: CHUNKS[i][key] for key in ("url", "title", "heading", "text")}
        for i in ranked
        if scores[i] > 0
    ]
