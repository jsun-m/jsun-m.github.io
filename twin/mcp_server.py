"""The remote MCP surface: `claude mcp add --transport http john-twin <URL>/mcp`.

Implemented as a plain FastAPI route speaking sessionless MCP streamable-HTTP
(JSON-RPC over POST, JSON response mode — spec-compliant; SSE is optional).
The official mcp SDK's ASGI app deadlocks under Beam's gunicorn/uvicorn
runtime, and a stateless twin doesn't need its session machinery anyway.
"""

import json

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from agent import run_turn_text
from persona import ABOUT_JOHN
from tools import search_beam_docs as _search_beam_docs

SUPPORTED_PROTOCOLS = {"2024-11-05", "2025-03-26", "2025-06-18", "2026-07-28"}
DEFAULT_PROTOCOL = "2025-06-18"

SERVER_INFO = {"name": "john-marshall-twin", "version": "1.0.0"}
INSTRUCTIONS = (
    "John Marshall's agentic twin — consult it about beam.cloud (serverless "
    "GPU infra), agentic systems (MCP, AG2/AutoGen, observability), or code "
    "design. ask_john_twin is conversational; search_beam_docs and about_john "
    "are deterministic lookups."
)

TOOLS = [
    {
        "name": "ask_john_twin",
        "description": (
            "Ask John Marshall's agentic twin a question — Beam infrastructure, "
            "agentic systems (MCP/AG2), or code advice. Optionally pass code or "
            "background as context."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question to ask"},
                "context": {"type": "string", "description": "Optional code or background context"},
            },
            "required": ["question"],
        },
    },
    {
        "name": "search_beam_docs",
        "description": (
            "Keyword-search the current beam.cloud documentation. Returns JSON "
            "chunks with url/heading/text. Deterministic — no LLM involved."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query"}},
            "required": ["query"],
        },
    },
    {
        "name": "about_john",
        "description": "Who is John Marshall? Background, open-source track record, contact info.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


async def _call_tool(name: str, args: dict) -> str:
    if name == "ask_john_twin":
        question = args.get("question", "")
        context = args.get("context")
        content = f"[context]\n{context}\n[/context]\n\n{question}" if context else question
        return await run_turn_text([{"role": "user", "content": content}])
    if name == "search_beam_docs":
        return _search_beam_docs(args.get("query", ""))
    if name == "about_john":
        return ABOUT_JOHN
    raise KeyError(name)


def _result(req_id, result: dict) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id, code: int, message: str, status: int = 200) -> JSONResponse:
    return JSONResponse(
        {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}},
        status_code=status,
    )


async def mcp_route(request: Request):
    if request.method != "POST":
        # No server-initiated SSE stream and no sessions to delete.
        return Response(status_code=405, headers={"Allow": "POST"})
    try:
        body = json.loads(await request.body())
    except json.JSONDecodeError:
        return _error(None, -32700, "parse error", status=400)

    method = body.get("method", "")
    req_id = body.get("id")

    # Notifications and responses get 202 + no body per streamable-HTTP spec.
    if req_id is None:
        return Response(status_code=202)

    if method == "initialize":
        client_proto = (body.get("params") or {}).get("protocolVersion", "")
        proto = client_proto if client_proto in SUPPORTED_PROTOCOLS else DEFAULT_PROTOCOL
        return _result(req_id, {
            "protocolVersion": proto,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": INSTRUCTIONS,
        })
    if method == "ping":
        return _result(req_id, {})
    if method == "tools/list":
        return _result(req_id, {"tools": TOOLS})
    if method == "tools/call":
        params = body.get("params") or {}
        name = params.get("name", "")
        args = params.get("arguments") or {}
        try:
            text = await _call_tool(name, args)
            return _result(req_id, {"content": [{"type": "text", "text": text}], "isError": False})
        except KeyError:
            return _error(req_id, -32602, f"unknown tool: {name}")
        except Exception as e:  # noqa: BLE001 — report as a tool error, not a 500
            return _result(req_id, {
                "content": [{"type": "text", "text": f"tool failed: {type(e).__name__}"}],
                "isError": True,
            })
    if method in ("resources/list", "prompts/list"):
        key = method.split("/")[0]
        return _result(req_id, {key: []})
    return _error(req_id, -32601, f"method not found: {method}")
