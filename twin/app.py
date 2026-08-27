"""Beam entrypoint. Deploy: beam deploy app.py:handler"""

from beam import Image, asgi


@asgi(
    name="john-twin",
    image=Image(
        python_version="python3.12",
        python_packages=[
            "ag2[openai,gemini] @ git+https://github.com/ag2ai/ag2.git@845324d913dfdb81cf75e3c4655c13a225aa1257",
            "fastapi>=0.115",
            "rank-bm25==0.2.2",
            "httpx>=0.27",
        ],
    ),
    cpu=1.0,
    memory=1024,
    # TWIN_PROVIDER switches the LLM (gemini | deepseek | openai) — add the
    # matching *_API_KEY secret here when switching off the Gemini default.
    secrets=["GEMINI_API_KEY"],
    authorized=False,  # public app; selective auth + rate limits live in server.py
    keep_warm_seconds=300,
)
def handler(context):
    from server import build_app

    return build_app()
