"""Tool schemas + implementations shared by the agent loop and the MCP server."""

import json

from docs_index.search import search
from persona import ABOUT_JOHN

TOOL_RESULT_MAX_CHARS = 6000


def search_beam_docs(query: str, k: int = 5) -> str:
    """Search the Beam (beam.cloud) docs; returns JSON chunks with url/heading/text."""
    results = search(query, k=min(int(k), 8))
    if not results:
        return "No matching Beam docs found. The docs may not cover this — say so."
    out = json.dumps(results, indent=1)
    return out[:TOOL_RESULT_MAX_CHARS]


def about_john() -> str:
    """Deterministic summary of who John is."""
    return ABOUT_JOHN


TOOL_SCHEMAS = [
    {
        "name": "search_beam_docs",
        "description": (
            "Search the current beam.cloud documentation (BM25 over docs.beam.cloud). "
            "Call this BEFORE answering any question about Beam features, APIs, "
            "deployment, pricing, or limits. Returns chunks with url, heading, text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "k": {"type": "integer", "description": "Number of chunks (default 5, max 8)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "about_john",
        "description": "Get the factual summary of John Marshall's background and contact info.",
        "input_schema": {"type": "object", "properties": {}},
    },
]

TOOL_IMPLS = {
    "search_beam_docs": search_beam_docs,
    "about_john": about_john,
}
