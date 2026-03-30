# Lab 6 — Tracing & Evaluation

Set up tracing for MCP servers via Phoenix and evaluation via Pydantic Evals.

## Prerequisites

- Lab5 deployed (Phoenix + Qdrant running in cluster)
- Phoenix UI: http://phoenix.aire2026.local
- Phoenix OTLP gRPC: `phoenix.aire2026.local:4317` (or `phoenix.observability.svc.cluster.local:4317` from within the cluster)
- Python 3.12+

## Tasks

### 1. MCP Server Tracing

Add OpenTelemetry tracing to an MCP server so every tool call appears as a span in Phoenix.

**Docs:** https://arize.com/docs/phoenix/integrations/python/mcp-tracing

```bash
cd Lab6/tracing
pip install -r requirements.txt
```

**Example:** `tracing/mcp_tracing_example.py` — knowledge-base MCP server with Phoenix tracing.

Key steps:
1. Configure `TracerProvider` with OTLP exporter pointing at Phoenix endpoint
2. Attach `MCPInstrumentor` from `openinference-instrumentation-mcp`
3. Add custom spans for tool calls
4. Start the server and verify traces in Phoenix UI

```bash
# Run with tracing
PHOENIX_COLLECTOR_ENDPOINT=http://phoenix.aire2026.local:4317 \
KB_API_BASE_URL=http://localhost:8000 \
python mcp_tracing_example.py
```

### 2. Tracing Overview

Walk through the OpenAI Agents Cookbook to understand tracing in the context of AI agents:

**Colab:** https://colab.research.google.com/github/Arize-ai/phoenix/blob/c02f0e7d807129952afa5da430299aec32fafcc9/tutorials/evals/openai_agents_cookbook.ipynb

Key concepts:
- **Spans** — individual operations (tool call, LLM request)
- **Traces** — a chain of spans from request to response
- **Attributes** — metadata on spans (input, output, latency)
- Phoenix UI for trace visualization and analysis

### 3. Evaluation with Pydantic Evals

Set up an evaluation pipeline for MCP servers.

**Docs:** https://arize.com/docs/phoenix/integrations/python/pydantic/pydantic-evals#command-line

```bash
cd Lab6/evaluation
pip install -r requirements.txt
python pydantic_evals_example.py
```

**Example:** `evaluation/pydantic_evals_example.py` — basic eval framework with Pydantic models.

Key steps:
1. Define `EvalCase` — input + expected output
2. Run agent/MCP tool with test input
3. Verify response against expectations
4. Send eval traces to Phoenix for analysis

## Structure

```
Lab6/
├── README.md
├── tracing/
│   ├── mcp_tracing_example.py   # Knowledge-base MCP with Phoenix tracing
│   ├── requirements.txt
│   └── env.example
└── evaluation/
    ├── pydantic_evals_example.py # Eval framework with Pydantic
    └── requirements.txt
```

## Architecture

```
┌─────────────────┐    OTLP/gRPC     ┌──────────────┐
│  MCP Server     │ ───────────────── │  Phoenix     │
│  (traced)       │    :4317          │  (Lab5)      │
└─────────────────┘                   └──────────────┘
        │                                    │
        │ stdio                              │ UI
        ▼                                    ▼
┌─────────────────┐                   http://phoenix.aire2026.local
│  kagent Agent   │
│  (assistant)    │
└─────────────────┘
        │
        ▼
┌─────────────────┐
│  Eval Runner    │ ── traces ──► Phoenix
│  (pydantic)     │
└─────────────────┘
```
