"""App assembly. `uvicorn server:app` locally; Beam wraps build_app() in app.py."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from chat import chat_route
from mcp_server import mcp_route

DEFAULT_ORIGINS = (
    "http://localhost:8734,http://127.0.0.1:8734,https://jsun-m.github.io"
)


def build_app() -> FastAPI:
    app = FastAPI(title="john-marshall-twin")

    # Behind Beam's gateway (BETA9_GATEWAY_HOST set) the ingress already adds
    # permissive CORS headers on every response; adding our own produces a
    # duplicate Access-Control-Allow-Origin, which browsers reject wholesale.
    # Our allowlist middleware is for local/self-hosted runs only.
    if not os.environ.get("BETA9_GATEWAY_HOST"):
        origins = os.environ.get("TWIN_ALLOWED_ORIGINS", DEFAULT_ORIGINS).split(",")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[o.strip() for o in origins if o.strip()],
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )

    # optional static bearer on /mcp only (ships unset)
    token = os.environ.get("TWIN_MCP_TOKEN")
    if token:
        @app.middleware("http")
        async def mcp_auth(request, call_next):
            if request.url.path.startswith("/mcp"):
                if request.headers.get("authorization") != f"Bearer {token}":
                    return JSONResponse({"error": "unauthorized"}, status_code=401)
            return await call_next(request)

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    app.post("/chat")(chat_route)
    app.api_route("/mcp", methods=["POST", "GET", "DELETE"])(mcp_route)
    return app


app = build_app()
