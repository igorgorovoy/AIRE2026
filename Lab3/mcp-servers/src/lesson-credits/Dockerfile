# Збірка: контекст — КОРІНЬ agentic-ai-landing-zone (не цей каталог!)
#
#   cd /path/to/agentic-ai-landing-zone
#   docker build -t mcp-lesson-credits:latest \
#     -f /path/to/Lab3/mcp-servers/src/lesson-credits/Dockerfile .
#
# server.py лежить у mcp-servers-lesson-credits/server.py відносно кореня проєкту.
# _PROJECT_ROOT = Path(__file__).parents[1] → /app — і саме звідти підтягуються
# agents/ та core/ (локальні пакети проєкту).
FROM python:3.12-slim

WORKDIR /app

# Встановити залежності проєкту (langgraph, langchain-core, etc.) + MCP сервер
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir "mcp[cli]>=1.0" "python-dotenv>=1.0"

# Скопіювати локальні пакети-залежності сервера
COPY agents/ ./agents/
COPY core/ ./core/

# Скопіювати сам сервер (зберігаємо відносний шлях: parents[1] == /app)
COPY mcp-servers-lesson-credits/server.py ./mcp-servers-lesson-credits/server.py

# Storage backend: local (файлова система всередині контейнера)
# Для production змініть на lakefs і вкажіть LAKEFS_* через Secret
ENV STORAGE_BACKEND=local

CMD ["python", "mcp-servers-lesson-credits/server.py"]
