# Build context: agentic-ai-landing-zone repo ROOT (not this directory!)
#
#   cd /path/to/agentic-ai-landing-zone
#   docker build -t mcp-tasks:latest \
#     -f /path/to/Lab3/mcp-servers/src/tasks/Dockerfile .
#
# server.py lives at mcp-servers-tasks/server.py relative to project root.
# _PROJECT_ROOT = Path(__file__).parents[1] → /app — agents/, core/, scripts/ load from there.
FROM python:3.12-slim

WORKDIR /app

# Project deps (langgraph, langchain-core, etc.) + MCP server
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir "mcp[cli]>=1.0" "python-dotenv>=1.0"

# Local packages the server imports
COPY agents/ ./agents/
COPY core/ ./core/
# scripts/ needed for tasks_sync_beads (beads_to_tasks_sync.py)
COPY scripts/ ./scripts/

# Server module (keep relative path: parents[1] == /app)
COPY mcp-servers-tasks/server.py ./mcp-servers-tasks/server.py

# Storage: local (filesystem inside container)
# For production switch to lakefs and set LAKEFS_* via Secret
ENV STORAGE_BACKEND=local
# Delete tools off by default (safety)
ENV ENABLE_DELETE_TOOLS=0

CMD ["python", "mcp-servers-tasks/server.py"]
