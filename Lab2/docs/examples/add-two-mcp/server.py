#!/usr/bin/env python3
"""Minimal MCP server: add_two_numbers tool for the kagent lab."""

from fastmcp import FastMCP

mcp = FastMCP("Add Two Numbers")


@mcp.tool()
def add_two_numbers(a: int, b: int) -> int:
    """Return the sum of integers a and b."""
    return a + b


if __name__ == "__main__":
    # No banner on stdout — stdio MCP transport must keep stdout for the protocol only.
    mcp.run(show_banner=False)
