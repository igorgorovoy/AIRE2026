# Lab 4 — A2A Protocol: Agent-to-Agent Communication

> **Мета:** ознайомитися з протоколом A2A (Agent-to-Agent), реалізувати агента з Agent Card та Well-Known URI, налаштувати міжагентну комунікацію, розгорнути Inventory AI-ресурсів у кластері.

## A2A Protocol — огляд

**A2A (Agent2Agent)** — відкритий протокол для стандартизованої комунікації між AI-агентами. Розроблений Google, переданий Linux Foundation. Підтримується 150+ організаціями.

### Ключові відмінності від MCP

| Аспект | MCP | A2A |
|--------|-----|-----|
| **Фокус** | Агент ↔ Інструменти/Дані | Агент ↔ Агент |
| **Модель** | Агент викликає tools | Агенти спілкуються як рівноправні |
| **Discovery** | Конфігурація клієнта | Well-Known URI (`/.well-known/agent-card.json`) |
| **Протокол** | JSON-RPC (stdio/SSE) | JSON-RPC (HTTP/gRPC) |
| **Стан** | Stateless tool calls | Stateful Tasks (lifecycle) |

### Основні концепції A2A

```
┌─────────────────────────────────────────────────────────────┐
│                    A2A Protocol Flow                         │
│                                                              │
│  1. Discovery:  GET /.well-known/agent-card.json            │
│  2. Send Task:  POST / (JSON-RPC: a2a.SendMessage)          │
│  3. Get Task:   POST / (JSON-RPC: a2a.GetTask)              │
│  4. Cancel:     POST / (JSON-RPC: a2a.CancelTask)           │
└─────────────────────────────────────────────────────────────┘

Agent Card — JSON-документ з метаданими агента:
  - name, description, version
  - skills[] — можливості агента
  - capabilities — streaming, push notifications
  - supported_interfaces — endpoint URLs
  - securitySchemes — автентифікація

Task States:
  CREATED → WORKING → COMPLETED
                    → FAILED
                    → CANCELED
           → INPUT_REQUIRED → WORKING → ...
           → AUTH_REQUIRED → WORKING → ...
           → REJECTED
```

## Архітектура Lab4

```
┌───────────────────────────────────────────────────────────┐
│                     User / Client                         │
└──────────────────────┬────────────────────────────────────┘
                       │ A2A JSON-RPC
          ┌────────────▼────────────┐
          │   Orchestrator Agent    │  (port 9001)
          │   /.well-known/         │
          │    agent-card.json      │
          │                         │
          │   Skills:               │
          │   - orchestration       │
          │   (discover & delegate) │
          └────────────┬────────────┘
                       │ 1. GET /.well-known/agent-card.json
                       │ 2. POST a2a.SendMessage
          ┌────────────▼────────────┐
          │   Assistant Agent       │  (port 9000)
          │   /.well-known/         │
          │    agent-card.json      │
          │                         │
          │   Skills:               │
          │   - knowledge_base      │
          │   - lesson_credits      │
          │   - task_manager        │
          └──┬──────┬───────┬───────┘
             │      │       │
         ┌───▼──┐┌──▼──┐┌───▼───┐
         │ KB   ││Less.││ Tasks │  (Lab3 MCP backends)
         │ API  ││Cred.││ Mgr   │
         └──────┘└─────┘└───────┘
```

## Структура Lab4

```
Lab4/
├── LAB4.md                              ← цей файл
├── a2a-agents/
│   ├── requirements.txt                 ← a2a-sdk[http-server], uvicorn, httpx
│   ├── docker-compose.yaml              ← локальний запуск обох агентів
│   ├── Dockerfile.assistant             ← Docker-образ assistant agent
│   ├── Dockerfile.orchestrator          ← Docker-образ orchestrator agent
│   ├── test_a2a.py                      ← тестовий клієнт
│   └── src/
│       ├── assistant-agent/
│       │   ├── __main__.py              ← Agent Card + A2A server setup
│       │   └── agent_executor.py        ← AgentExecutor з MCP tool routing
│       └── orchestrator-agent/
│           ├── __main__.py              ← Agent Card + A2A server setup
│           └── agent_executor.py        ← Discovery + delegation via A2A
├── manifests/
│   ├── k8s/
│   │   ├── namespace.yaml               ← namespace: a2a
│   │   ├── secrets-example.yaml         ← шаблон секретів
│   │   ├── assistant-agent.yaml         ← Deployment + Service
│   │   ├── orchestrator-agent.yaml      ← Deployment + Service
│   │   └── kustomization.yaml           ← Kustomize manifest
│   └── inventory/
│       └── abox-inventory.yaml          ← ConfigMap з переліком AI-ресурсів
└── docs/                                ← скріншоти та додаткова документація
```

## Компоненти

### 1. Assistant Agent (A2A Server)

**Файл:** `a2a-agents/src/assistant-agent/__main__.py`

Обгортка Lab3 MCP tools у A2A протокол:

- **Agent Card** з трьома skills (knowledge_base, lesson_credits, task_manager)
- **Well-Known URI**: `GET http://localhost:9000/.well-known/agent-card.json`
- **A2A endpoint**: `POST http://localhost:9000/` (JSON-RPC)
- Використовує `a2a-sdk`: `A2AStarletteApplication`, `DefaultRequestHandler`, `InMemoryTaskStore`

**AgentExecutor** (`agent_executor.py`):
- Отримує `a2a.SendMessage` → витягує текст з `message.parts`
- Маршрутизує за ключовими словами до KB/Lessons/Tasks tools
- Повертає результат як `TaskArtifactUpdateEvent` (TextPart)

### 2. Orchestrator Agent (A2A Client + Server)

**Файл:** `a2a-agents/src/orchestrator-agent/__main__.py`

Агент-оркестратор для міжагентної комунікації:

- **Discovery**: `GET /.well-known/agent-card.json` на кожному зареєстрованому агенті
- **Delegation**: надсилає `a2a.SendMessage` JSON-RPC до найкращого агента за skill matching
- **Команди**: `discover` — показати всіх агентів, інакше — делегувати задачу

### 3. Kubernetes Manifests

- **Namespace** `a2a` для ізоляції від kagent namespace
- **Deployments** з health checks через `/.well-known/agent-card.json`
- **Services** (ClusterIP) для внутрішньокластерної комунікації
- Orchestrator знаходить assistant через DNS: `a2a-assistant-agent.a2a.svc.cluster.local:9000`

### 4. Inventory

ConfigMap `ai-inventory-config` у namespace kagent — перелік всіх AI-ресурсів у кластері:
- Агенти (kagent Lab3 + A2A Lab4)
- MCP сервери
- Інфраструктурні компоненти

## Швидкий старт

### Передумови

- Python 3.12+
- Docker + Docker Compose (для контейнерного запуску)
- kubectl + доступ до кластера (для K8s deployment)

### Локальний запуск

```bash
cd Lab4/a2a-agents

# 1. Створити virtualenv
python -m venv .venv
source .venv/bin/activate

# 2. Встановити залежності
pip install -r requirements.txt

# 3. Запустити Assistant Agent (термінал 1)
cd src/assistant-agent
python __main__.py
# → Agent Card: http://localhost:9000/.well-known/agent-card.json

# 4. Запустити Orchestrator Agent (термінал 2)
cd src/orchestrator-agent
python __main__.py
# → Agent Card: http://localhost:9001/.well-known/agent-card.json
```

### Docker Compose

```bash
cd Lab4/a2a-agents
docker compose up --build
```

### Перевірка Agent Card (Well-Known URI)

```bash
# Assistant Agent Card
curl -s http://localhost:9000/.well-known/agent-card.json | jq .

# Orchestrator Agent Card
curl -s http://localhost:9001/.well-known/agent-card.json | jq .
```

Очікуваний результат (assistant):
```json
{
  "name": "Personal Assistant Agent",
  "description": "Персональний AI-асистент з доступом до Knowledge Base...",
  "version": "1.0.0",
  "skills": [
    {"id": "knowledge_base", "name": "Knowledge Base", ...},
    {"id": "lesson_credits", "name": "Lesson Credits", ...},
    {"id": "task_manager", "name": "Task Manager", ...}
  ],
  "capabilities": {"streaming": false, "push_notifications": false},
  "supported_interfaces": [{"protocol_binding": "JSONRPC", "url": "http://localhost:9000"}]
}
```

### Відправка A2A Task

```bash
# Надіслати повідомлення Assistant Agent
curl -s -X POST http://localhost:9000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "a2a.SendMessage",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"type": "text", "text": "Покажи список документів"}]
      }
    }
  }' | jq .
```

### Міжагентна комунікація (Orchestrator → Assistant)

```bash
# Orchestrator виявляє агентів
curl -s -X POST http://localhost:9001/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "a2a.SendMessage",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"type": "text", "text": "discover"}]
      }
    }
  }' | jq .

# Orchestrator делегує задачу до Assistant
curl -s -X POST http://localhost:9001/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "2",
    "method": "a2a.SendMessage",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"type": "text", "text": "Покажи список документів"}]
      }
    }
  }' | jq .
```

### Тестовий скрипт

```bash
# Тест assistant
python test_a2a.py assistant

# Тест orchestrator (delegation)
python test_a2a.py orchestrator

# Discovery обох агентів
python test_a2a.py discover
```

## Kubernetes Deployment

### Збірка Docker-образів

```bash
cd Lab4/a2a-agents

# Збірка образів
docker build -f Dockerfile.assistant -t a2a-assistant-agent:latest .
docker build -f Dockerfile.orchestrator -t a2a-orchestrator-agent:latest .

# Для Rancher Desktop
rdctl shell ctr -n k8s.io images import < <(docker save a2a-assistant-agent:latest)
rdctl shell ctr -n k8s.io images import < <(docker save a2a-orchestrator-agent:latest)
```

### Розгортання

```bash
# Option A: Kustomize
kubectl apply -k Lab4/manifests/k8s/

# Option B: Послідовно
kubectl apply -f Lab4/manifests/k8s/namespace.yaml
kubectl apply -f Lab4/manifests/k8s/secrets-example.yaml  # або secrets.yaml
kubectl apply -f Lab4/manifests/k8s/assistant-agent.yaml
kubectl apply -f Lab4/manifests/k8s/orchestrator-agent.yaml
```

### Inventory (перелік AI-ресурсів)

```bash
# Розгорнути inventory ConfigMap
kubectl apply -f Lab4/manifests/inventory/abox-inventory.yaml

# Переглянути всі AI-ресурси в кластері
kubectl get agents,mcpservers -n kagent
kubectl get deployments -n a2a

# Переглянути inventory
kubectl get configmap ai-inventory-config -n kagent -o yaml
```

### Перевірка

```bash
# Pods status
kubectl get pods -n a2a

# Agent Card через port-forward
kubectl port-forward svc/a2a-assistant-agent -n a2a 9000:9000 &
curl -s http://localhost:9000/.well-known/agent-card.json | jq .

# Logs
kubectl logs -n a2a -l app=a2a-assistant-agent --tail=50
kubectl logs -n a2a -l app=a2a-orchestrator-agent --tail=50
```

## Infrastructure (Advanced)

### MCPG — MCP Security Governance

Для розгортання MCP Security Governance у кластері:

```bash
# Клонувати репозиторій
git clone https://github.com/techwithhuz/mcp-security-governance.git

# Розгорнути за інструкціями README
# MCPG дозволяє:
# - Контроль доступу до MCP серверів
# - Audit logging MCP tool calls
# - Policy enforcement для AI агентів
```

## Змінні середовища

| Агент | Змінна | Значення за замовч. | Опис |
|-------|--------|---------------------|------|
| assistant | `KB_API_BASE_URL` | `http://localhost:8000` | URL Knowledge Base backend |
| assistant | `KB_API_KEY` | `""` | API Key для KB |
| orchestrator | `A2A_AGENT_URLS` | `http://localhost:9000` | Comma-separated URLs агентів |

## Troubleshooting

| Проблема | Рішення |
|----------|---------|
| `Connection refused` на 9000 | Перевірте що assistant agent запущений |
| Agent Card повертає 404 | Перевірте URL: `/.well-known/agent-card.json` (не `agent.json`) |
| Orchestrator не бачить assistant | Перевірте `A2A_AGENT_URLS` та мережеву доступність |
| K8s pods CrashLoopBackOff | `kubectl logs -n a2a <pod>` — перевірте залежності |
| `ModuleNotFoundError: a2a` | `pip install "a2a-sdk[http-server]"` |

## Корисні посилання

- [A2A Protocol Specification](https://a2a-protocol.org/latest/)
- [a2a-python SDK (GitHub)](https://github.com/google-a2a/a2a-python)
- [A2A Samples](https://github.com/a2aproject/a2a-samples)
- [MCPG Security Governance](https://github.com/techwithhuz/mcp-security-governance)
- [Google Blog: A2A Protocol Upgrade](https://cloud.google.com/blog/products/ai-machine-learning/agent2agent-protocol-is-getting-an-upgrade)
