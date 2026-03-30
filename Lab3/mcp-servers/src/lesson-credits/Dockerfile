# Build context: agentic-ai-landing-zone repo ROOT (not this directory!)
#
#   cd /path/to/agentic-ai-landing-zone
#   docker build -t mcp-lesson-credits:latest \
#     -f /path/to/Lab3/mcp-servers/src/lesson-credits/Dockerfile .
#
# server.py lives at mcp-servers-lesson-credits/server.py relative to project root.
# _PROJECT_ROOT = Path(__file__).parents[1] → /app — agents/ and core/ load from there.
FROM python:3.12-slim

WORKDIR /app

# Project deps (langgraph, langchain-core, etc.) + MCP server
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir "mcp[cli]>=1.0" "python-dotenv>=1.0"

# Local packages the server imports
COPY agents/ ./agents/
COPY core/ ./core/

# Server module (keep relative path: parents[1] == /app)
COPY mcp-servers-lesson-credits/server.py ./mcp-servers-lesson-credits/server.py

# Storage: local (filesystem inside container)
# For production switch to lakefs and set LAKEFS_* via Secret
ENV STORAGE_BACKEND=local

CMD ["python", "mcp-servers-lesson-credits/server.py"]
