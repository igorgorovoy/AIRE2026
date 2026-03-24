# Lab 3 — Персональний асистент із трьома MCP-серверами

> **Мета:** розгорнути в Kubernetes (через kagent) агента-асистента, який через три MCP-сервери має доступ до Knowledge Base, обліку уроків та менеджера задач.

## Архітектура

```
┌─────────────────────────────────────────────┐
│              kagent UI / Chat               │
└──────────────────┬──────────────────────────┘
                   │
         ┌─────────▼─────────┐
         │  assistant-agent  │  (Agent kagent.dev/v1alpha2)
         │  modelConfig:     │
         │  default-model-   │
         │  config           │
         └──┬──────┬──────┬──┘
            │      │      │
    ┌───────▼─┐ ┌──▼──────┐ ┌────────▼────────┐
    │  mcp-   │ │  mcp-   │ │   mcp-tasks     │
    │knowledge│ │lesson-  │ │                 │
    │ -base   │ │credits  │ │ Task Manager    │
    │         │ │         │ │ workspaces,     │
    │ Obsidian│ │ English │ │ boards, cards   │
    │ vault   │ │  Mary   │ │ comments, etc.  │
    └────┬────┘ └────┬────┘ └────────┬────────┘
         │           │               │
    HTTP API    local/lakeFS    local/lakeFS
    (backend)    storage          storage
```

## Структура Lab3

```
Lab3/
├── LAB3.md                                ← цей файл
├── mcp-servers/
│   └── src/
│       ├── knowledge-base/
│       │   ├── Dockerfile                 ← автономний образ
│       │   └── server.py                  ← копія з agentic-ai-landing-zone
│       ├── lesson-credits/
│       │   ├── Dockerfile                 ← збірка з кореня ALZ
│       │   └── server.py                  ← копія з agentic-ai-landing-zone
│       └── tasks/
│           ├── Dockerfile                 ← збірка з кореня ALZ
│           └── server.py                  ← копія з agentic-ai-landing-zone
└── manifests/
    └── kagent/
        └── assistant/
            ├── README.md
            ├── mcpserver-knowledge-base.yaml
            ├── mcpserver-lesson-credits.yaml
            ├── mcpserver-tasks.yaml
            ├── agent.yaml
            ├── all-in-one.yaml            ← 3 MCPServer + Agent в одному файлі
            └── kustomization.yaml
```

## MCP-сервери

| Образ | Джерело | Залежності |
|-------|---------|------------|
| `mcp-knowledge-base:latest` | `mcp-servers/src/knowledge-base/` | `mcp[cli]`, `python-dotenv` |
| `mcp-lesson-credits:latest` | корінь `agentic-ai-landing-zone` | + `langgraph`, `langchain-core`, `agents/`, `core/` |
| `mcp-tasks:latest` | корінь `agentic-ai-landing-zone` | + `langgraph`, `langchain-core`, `agents/`, `core/`, `scripts/` |

### Змінні середовища

| Сервер | Змінна | Значення за замовч. | Опис |
|--------|--------|---------------------|------|
| knowledge-base | `KB_API_BASE_URL` | `http://localhost:8000` | URL KB backend (viz/backend) |
| knowledge-base | `API_KEY` | `""` | X-API-Key header (якщо потрібен) |
| lesson-credits | `STORAGE_BACKEND` | `local` | `local` або `lakefs` |
| tasks | `STORAGE_BACKEND` | `local` | `local` або `lakefs` |
| tasks | `ENABLE_DELETE_TOOLS` | `0` | `1` — увімкнути інструменти видалення |
| lesson-credits, tasks | `LAKEFS_ENDPOINT` | — | для `STORAGE_BACKEND=lakefs` |
| lesson-credits, tasks | `LAKEFS_ACCESS_KEY` | — | для lakeFS |
| lesson-credits, tasks | `LAKEFS_SECRET_KEY` | — | для lakeFS |

## Передумови

1. **kagent** задеплоєний у namespace `kagent` (CRDs: `mcpservers.kagent.dev`, `agents.kagent.dev`).
2. **ModelConfig** `default-model-config` і Secret з API key провайдера (OpenAI або інший).
3. **Docker** і доступ до Kubernetes (`kubectl`).
4. (Опційно) **agentic-ai-landing-zone** проєкт — для збірки `lesson-credits` і `tasks` образів.

```bash
# Перевірка kagent
kubectl get modelconfigs,mcpservers,agents -n kagent
```

## Крок 1 — Зібрати Docker-образи

Визначте шляхи до репозиторіїв:

```bash
export LAB3=/path/to/AIRE2026/Lab3
export ALZ=/path/to/agentic-ai-landing-zone
```

### knowledge-base

```bash
docker build -t mcp-knowledge-base:latest "$LAB3/mcp-servers/src/knowledge-base"
```

### lesson-credits

```bash
docker build -t mcp-lesson-credits:latest \
  -f "$LAB3/mcp-servers/src/lesson-credits/Dockerfile" "$ALZ"
```

### tasks

```bash
docker build -t mcp-tasks:latest \
  -f "$LAB3/mcp-servers/src/tasks/Dockerfile" "$ALZ"
```

### Rancher Desktop / k3s (без реєстру)

Якщо Kubernetes не бачить образи після `docker build` — завантажте їх у VM:

```bash
for img in mcp-knowledge-base mcp-lesson-credits mcp-tasks; do
  docker save "${img}:latest" -o ~/"${img}.tar"
  rdctl shell -- sh -lc "sudo docker load -i ~/${img}.tar"
done
```

## Крок 2 — Налаштувати KB_API_BASE_URL

У файлі `manifests/kagent/assistant/mcpserver-knowledge-base.yaml` вкажіть актуальний URL backend-сервісу:

```yaml
env:
  - name: KB_API_BASE_URL
    value: "http://<service>.<namespace>.svc.cluster.local:8000"
```

Або відредагуйте `all-in-one.yaml`, якщо використовуєте його.

## Крок 3 — Застосувати маніфести

З **кореня Lab3** — обрати **один** варіант:

```bash
# Варіант A — один файл
kubectl apply -f manifests/kagent/assistant/all-in-one.yaml

# Варіант B — Kustomize
kubectl apply -k manifests/kagent/assistant

# Варіант C — по черзі
kubectl apply -f manifests/kagent/assistant/mcpserver-knowledge-base.yaml
kubectl apply -f manifests/kagent/assistant/mcpserver-lesson-credits.yaml
kubectl apply -f manifests/kagent/assistant/mcpserver-tasks.yaml
kubectl apply -f manifests/kagent/assistant/agent.yaml
```

## Крок 4 — Перевірка

```bash
# Стан ресурсів
kubectl get mcpservers,agents -n kagent
kubectl get pods -n kagent | grep -E 'mcp-|NAME'

# Деталі
kubectl describe mcpserver mcp-knowledge-base -n kagent
kubectl describe mcpserver mcp-lesson-credits  -n kagent
kubectl describe mcpserver mcp-tasks           -n kagent
kubectl describe agent     assistant-agent     -n kagent

# Логи MCP-серверів
kubectl logs -n kagent -l app.kubernetes.io/name=mcp-knowledge-base  --tail=30
kubectl logs -n kagent -l app.kubernetes.io/name=mcp-lesson-credits  --tail=30
kubectl logs -n kagent -l app.kubernetes.io/name=mcp-tasks           --tail=30
```

Очікується: поди у стані `Running`, агент `Ready` / `Accepted`.

## Крок 5 — Відкрити kagent UI

```bash
kubectl -n agentgateway-system port-forward svc/agentgateway-external 8080:80
```

Браузер: **http://127.0.0.1:8080/** → оберіть **assistant-agent**.

### Приклади запитів для перевірки

**Knowledge Base:**
```
Знайди документ про AWS Skill Builder у knowledge base
Скільки документів у базі знань?
```

**Lesson Credits:**
```
Скільки уроків English. Mary залишилось?
Спиши 1 урок для English. Mary
```

**Task Manager:**
```
Покажи всі workspaces
Створи картку "Перевірити Lab3" у списку To Do на дошці Work
```

## Видалення

```bash
kubectl delete -f manifests/kagent/assistant/all-in-one.yaml
# або
kubectl delete -k manifests/kagent/assistant
```

## Troubleshooting

Детальний troubleshooting → [`manifests/kagent/assistant/README.md`](manifests/kagent/assistant/README.md).

### Швидка діагностика

```bash
# Контролер kagent
kubectl logs -n kagent -l app.kubernetes.io/name=kagent-controller --tail=100

# Перезапустити под MCP після переробки образу
kubectl rollout restart deployment -n kagent -l app.kubernetes.io/name=mcp-lesson-credits
```

### Дані зникають після рестарту поду

За замовчуванням `STORAGE_BACKEND=local` — дані живуть в `emptyDir` всередині контейнера.  
Для persistence додайте `PersistentVolumeClaim` або переключіться на lakeFS.

### ModuleNotFoundError: agents / core

Образ зібрано не з кореня `agentic-ai-landing-zone`. Переконайтесь:
```bash
# Перевірка правильного контексту збірки
docker build -t mcp-lesson-credits:latest \
  -f "$LAB3/mcp-servers/src/lesson-credits/Dockerfile" \
  "$ALZ"   # ← контекст = корінь ALZ
```
