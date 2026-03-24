# Збірка: з каталогу mcp-servers/src/knowledge-base (автономний сервер, без зовнішніх залежностей проєкту)
#   docker build -t mcp-knowledge-base:latest .
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir "mcp[cli]>=1.0" "python-dotenv>=1.0"

COPY server.py .

CMD ["python", "server.py"]
