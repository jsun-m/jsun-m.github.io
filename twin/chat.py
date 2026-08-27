"""POST /chat — SSE stream of TurnEvents for the portfolio widget."""

import json

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

import ratelimit
from agent import run_turn

MAX_BODY_BYTES = 32_768


async def chat_route(request: Request):
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        return JSONResponse({"error": "payload too large"}, status_code=413)
    try:
        payload = json.loads(body)
        messages = payload["messages"]
        assert isinstance(messages, list) and messages
        assert all(m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)
                   for m in messages)
        assert messages[-1]["role"] == "user"
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "expected {messages: [{role, content}...]} ending with a user message"},
                            status_code=422)

    ip = ratelimit.client_ip(request.headers, request.client.host if request.client else "?")
    limited = ratelimit.check(ip)
    if limited:
        return JSONResponse({"error": limited}, status_code=429)

    async def stream():
        async for event in run_turn(messages):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
