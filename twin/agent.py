"""The shared per-turn agent loop (both the chat SSE route and the MCP `ask`
tool consume this). Stateless: the caller supplies the full message history.

Framework: AG2 (the same beta `Agent` API as the agentos universal agent —
pinned to the rev agentos uses). LLM: provider-switchable via model_config.py
(TWIN_PROVIDER = gemini | deepseek | openai; Gemini is the default).

Per turn we build a fresh `MemoryStream`, seed it with the prior conversation
(`stream.history.replace`), subscribe pumps for token/tool events, and drive
`Agent.ask()` — the agentos `turn.py`/`universal.py` pattern, single-tenant.

Yields TurnEvent dicts:
  {"type": "token", "text": str}
  {"type": "tool_call", "name": str, "input": dict}
  {"type": "tool_result", "name": str}
  {"type": "done"}
  {"type": "error", "message": str}
"""

import asyncio
import json
from typing import Annotated, AsyncIterator

from ag2 import Agent, MemoryStream, tool
from ag2.events import (
    ModelMessage,
    ModelMessageChunk,
    ModelRequest,
    ModelResponse,
    TextInput,
    ToolCallEvent,
    ToolResultEvent,
)
from pydantic import Field

import tools as impls
from model_config import build_model_config
from persona import PERSONA

TURN_TIMEOUT_SECONDS = 120
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_CHARS = 24_000


@tool
def search_beam_docs(
    query: Annotated[str, Field(description="Search query for the beam.cloud docs")],
    k: Annotated[int, Field(description="Number of chunks to return (default 5, max 8)")] = 5,
) -> str:
    """Search the current beam.cloud documentation (BM25 over docs.beam.cloud).
    Call this BEFORE answering any question about Beam features, APIs,
    deployment, pricing, or limits. Returns chunks with url, heading, text."""
    return impls.search_beam_docs(query, k)


@tool
def about_john() -> str:
    """Get the factual summary of John Marshall's background and contact info."""
    return impls.about_john()


_agent = Agent(
    "john-twin",
    config=build_model_config(streaming=True),
    prompt=PERSONA,
    tools=[search_beam_docs, about_john],
)


def _trim_history(messages: list[dict]) -> list[dict]:
    trimmed = messages[-MAX_HISTORY_MESSAGES:]
    while len(trimmed) > 1 and sum(len(str(m.get("content", ""))) for m in trimmed) > MAX_HISTORY_CHARS:
        trimmed = trimmed[1:]
    while trimmed and trimmed[0].get("role") != "user":
        trimmed = trimmed[1:]
    return trimmed


def _seed_events(history: list[dict]) -> list:
    events = []
    for m in history:
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if m["role"] == "user":
            events.append(ModelRequest([TextInput(content)]))
        else:
            events.append(ModelResponse(message=ModelMessage(content)))
    return events


def _tool_input(ev: ToolCallEvent) -> dict:
    args = getattr(ev, "arguments", None)
    if isinstance(args, dict):
        return args
    try:
        return json.loads(args or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


async def run_turn(messages: list[dict]) -> AsyncIterator[dict]:
    trimmed = _trim_history(messages)
    if not trimmed:
        yield {"type": "error", "message": "empty conversation"}
        return
    last_user = trimmed[-1]["content"]

    stream = MemoryStream()
    prior = _seed_events(trimmed[:-1])
    if prior:
        await stream.history.replace(prior)

    queue: asyncio.Queue = asyncio.Queue()
    SENTINEL = object()

    renders = [
        (ModelMessageChunk, lambda ev: {"type": "token", "text": ev.content or ""}),
        (ToolCallEvent, lambda ev: {"type": "tool_call", "name": ev.name, "input": _tool_input(ev)}),
        (ToolResultEvent, lambda ev: {"type": "tool_result", "name": ev.name}),
    ]

    async def pump(event_type, render):
        try:
            with stream.where(event_type).join() as events:
                async for ev in events:
                    await queue.put(render(ev))
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001 — a broken pump shouldn't kill the turn
            pass

    pumps = [asyncio.create_task(pump(et, r)) for et, r in renders]

    async def run_agent():
        try:
            await asyncio.wait_for(
                _agent.ask(last_user, stream=stream), timeout=TURN_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            await queue.put({"type": "error", "message": "turn timed out"})
        except Exception as e:  # noqa: BLE001 — surface as an event, not a 500
            await queue.put({"type": "error", "message": f"upstream error: {type(e).__name__}"})

    runner = asyncio.create_task(run_agent())

    async def watcher():
        try:
            await runner
        finally:
            await asyncio.sleep(0.05)  # let pumps drain trailing events
            await queue.put(SENTINEL)

    watch = asyncio.create_task(watcher())

    try:
        while True:
            item = await queue.get()
            if item is SENTINEL:
                break
            yield item
        yield {"type": "done"}
    finally:
        for t in (*pumps, runner, watch):
            t.cancel()


async def run_turn_text(messages: list[dict]) -> str:
    """Non-streaming convenience used by the MCP `ask` tool."""
    parts: list[str] = []
    async for event in run_turn(messages):
        if event["type"] == "token":
            parts.append(event["text"])
        elif event["type"] == "error":
            parts.append(f"\n[{event['message']}]")
    return "".join(parts).strip()
