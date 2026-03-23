#!/usr/bin/env python3
"""Мінімальний MCP-сервер: інструмент add_two_numbers для лабораторної kagent."""

from fastmcp import FastMCP

mcp = FastMCP("Add Two Numbers")


@mcp.tool()
def add_two_numbers(a: int, b: int) -> int:
    """Повертає суму двох цілих чисел a та b."""
    return a + b


if __name__ == "__main__":
    mcp.run()
