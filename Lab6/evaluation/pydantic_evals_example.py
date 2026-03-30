#!/usr/bin/env python3
"""Example: Pydantic Evals with Phoenix integration.

Based on: https://arize.com/docs/phoenix/integrations/python/pydantic/pydantic-evals

Evaluates an MCP-backed agent by running test cases and reporting results.
Traces are sent to Phoenix for visualization.

ENV:
  PHOENIX_COLLECTOR_ENDPOINT — Phoenix OTLP endpoint
  OPENAI_API_KEY — for LLM-based evaluations (or use agentgateway)
"""

import os

# ---------------------------------------------------------------------------
# 1. Configure Phoenix tracing (same as tracing example)
# ---------------------------------------------------------------------------
PHOENIX_ENDPOINT = os.getenv(
    "PHOENIX_COLLECTOR_ENDPOINT", "http://phoenix.aire2026.local:4317"
)

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

resource = Resource.create({"service.name": "mcp-evals"})
provider = TracerProvider(resource=resource)
exporter = OTLPSpanExporter(endpoint=PHOENIX_ENDPOINT, insecure=True)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

# ---------------------------------------------------------------------------
# 2. Define evaluation dataset with Pydantic
# ---------------------------------------------------------------------------
from pydantic import BaseModel


class EvalCase(BaseModel):
    """A single evaluation test case."""

    name: str
    input: str
    expected_contains: list[str]
    """Substrings that must appear in the agent response."""


# Test cases for the knowledge-base MCP server
EVAL_CASES: list[EvalCase] = [
    EvalCase(
        name="list_documents",
        input="List all documents in the knowledge base",
        expected_contains=["documents", ".md"],
    ),
    EvalCase(
        name="get_graph",
        input="Show me the knowledge base graph structure",
        expected_contains=["Nodes", "Edges"],
    ),
    EvalCase(
        name="search_topic",
        input="Find documents about AWS",
        expected_contains=["AWS"],
    ),
]


# ---------------------------------------------------------------------------
# 3. Run evaluations
# ---------------------------------------------------------------------------
def evaluate_response(case: EvalCase, response: str) -> dict:
    """Check if response contains expected substrings."""
    results = {}
    for expected in case.expected_contains:
        results[f"contains_{expected}"] = expected.lower() in response.lower()
    results["all_passed"] = all(results.values())
    return results


def run_evals():
    """Run all evaluation cases and print results."""
    tracer = trace.get_tracer("mcp-evals")
    print(f"Running {len(EVAL_CASES)} evaluation cases...\n")
    print(f"{'Case':<25} {'Pass':>6}  Details")
    print("-" * 60)

    passed = 0
    for case in EVAL_CASES:
        with tracer.start_as_current_span(
            f"eval:{case.name}",
            attributes={"eval.input": case.input, "eval.name": case.name},
        ):
            # In a real setup, this would call the MCP server via agent
            # For now, simulate with a placeholder
            response = f"[PLACEHOLDER] Response for: {case.input}"
            result = evaluate_response(case, response)

            status = "PASS" if result["all_passed"] else "FAIL"
            if result["all_passed"]:
                passed += 1
            print(f"{case.name:<25} {status:>6}  {result}")

    print("-" * 60)
    print(f"Results: {passed}/{len(EVAL_CASES)} passed")


if __name__ == "__main__":
    run_evals()
