"""System prompt assembly. persona.md is the personality-tuning seam."""

from pathlib import Path

_PERSONA_PATH = Path(__file__).parent / "persona.md"

PERSONA = _PERSONA_PATH.read_text(encoding="utf-8")

ABOUT_JOHN = (
    "John Marshall — Senior Software Engineer, Agentic Systems @ AG2 (formerly "
    "AutoGen); Founding Engineer @ Beam (beam.cloud, YC W22) 2021-2025, #4 "
    "all-time contributor to beam-cloud/beta9 (276 PRs: usage-based billing, "
    "analytics pipelines, task messaging, JS Sandbox SDK, checkpoint/restore "
    "for pods, auth & token systems). Ships MCP + agent-observability work in "
    "the AG2 ecosystem (ag2ai/ag2, Opik, OpenLLMetry, mcp-agent). USC alum, "
    "Gilbert AZ. GitHub: jsun-m · linkedin.com/in/jjmarsha · "
    "john.sun.marshall@gmail.com"
)
