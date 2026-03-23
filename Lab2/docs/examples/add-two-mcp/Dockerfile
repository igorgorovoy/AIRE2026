# Збірка: з каталогу add-two-mcp
#   docker build -t add-two-mcp:latest .
FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir "fastmcp>=2.0"

COPY server.py .

CMD ["python", "server.py"]
