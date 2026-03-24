# Збірка: контекст — КОРІНЬ agentic-ai-landing-zone (не цей каталог!)
#
#   cd /path/to/agentic-ai-landing-zone
#   docker build -t mcp-tasks:latest \
#     -f /path/to/Lab3/mcp-servers/src/tasks/Dockerfile .
#
# server.py лежить у mcp-servers-tasks/server.py відносно кореня проєкту.
# _PROJECT_ROOT = Path(__file__).parents[1] → /app — і саме звідти підтягуються
# agents/, core/ та scripts/ (локальні пакети/скрипти проєкту).
FROM python:3.12-slim

WORKDIR /app

# Встановити залежності проєкту (langgraph, langchain-core, etc.) + MCP сервер
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir "mcp[cli]>=1.0" "python-dotenv>=1.0"

# Скопіювати локальні пакети-залежності сервера
COPY agents/ ./agents/
COPY core/ ./core/
# scripts/ потрібен для tasks_sync_beads (beads_to_tasks_sync.py)
COPY scripts/ ./scripts/

# Скопіювати сам сервер (зберігаємо відносний шлях: parents[1] == /app)
COPY mcp-servers-tasks/server.py ./mcp-servers-tasks/server.py

# Storage backend: local (файлова система всередині контейнера)
# Для production змініть на lakefs і вкажіть LAKEFS_* через Secret
ENV STORAGE_BACKEND=local
# Інструменти видалення вимкнені за замовчуванням (безпека)
ENV ENABLE_DELETE_TOOLS=0

CMD ["python", "mcp-servers-tasks/server.py"]
