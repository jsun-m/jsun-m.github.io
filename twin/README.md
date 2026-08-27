# john-marshall-twin

John's agentic twin: one stateless FastAPI service exposing
- `POST /chat` — SSE stream consumed by the portfolio widget (`index.html`)
- `/mcp` — Streamable-HTTP MCP server (`ask_john_twin`, `search_beam_docs`, `about_john`)

Both surfaces share `agent.py:run_turn()` — an AG2 `Agent` (same beta API as
the agentos universal agent, pinned to the rev agentos uses). The LLM is
switchable via `model_config.py`: set `TWIN_PROVIDER` to `gemini` (default,
`gemini-3.5-flash`), `deepseek`, or `openai`, with `TWIN_MODEL` as an optional
override and the matching `*_API_KEY` env/secret.
Persona lives in `persona.md` — edit it to tune the twin's voice/knowledge.
Beam docs retrieval is BM25 over a committed artifact (v2: vector DB / KG behind
the same `docs_index/search.py:search()` interface).

## Local dev

```bash
cd twin
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python docs_index/build_index.py     # refresh the docs index artifact
GEMINI_API_KEY=... .venv/bin/uvicorn server:app --port 8787
```

- Widget: serve the portfolio root (`python3 -m http.server 8734`) and open
  `http://localhost:8734/?twin=http://127.0.0.1:8787`
- MCP: `claude mcp add --transport http twin-local http://127.0.0.1:8787/mcp`

## Deploy (Beam)

```bash
beam secret create GEMINI_API_KEY ...   # one time
cd twin && beam deploy app.py:handler
```

Take the printed `https://john-twin-....app.beam.cloud` URL and set it as
`TWIN_URL` in the `<script>` at the bottom of `../index.html`.

Config env (optional): `TWIN_ALLOWED_ORIGINS` (CORS allowlist),
`TWIN_MCP_TOKEN` (static bearer required on /mcp when set).

Cost guards: 6 model calls/turn, 2048 max_tokens/call, per-IP 4/min + 20/hr,
global 500 turns/day per container, persona block prompt-cached.
