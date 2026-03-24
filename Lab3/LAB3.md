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
| lesson-credits, tasks | `LAKEFS_ACCESS_KEY_ID` | — | Access Key ID для lakeFS |
| lesson-credits, tasks | `LAKEFS_SECRET_ACCESS_KEY` | — | Secret Key для lakeFS |
| lesson-credits, tasks | `LAKEFS_REPOSITORY` | — | назва репозиторію lakeFS |
| lesson-credits, tasks | `LAKEFS_BRANCH` | `main` | гілка lakeFS |

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

## Крок 2 — Створити Secret із credentials

MCP-сервери читають конфігурацію з Kubernetes Secret через механізм `secretRefs`. Secret монтується як файл `/secrets/<name>/dot-env` і зчитується через `python-dotenv`.

Скопіюйте приклад і заповніть реальними значеннями:

```bash
cp manifests/kagent/assistant/secrets-example.yaml \
   manifests/kagent/assistant/secrets.yaml
# відредагуйте secrets.yaml — вкажіть реальні endpoint, ключі тощо
```

Застосуйте Secret **до** маніфестів MCP-серверів:

```bash
kubectl apply -f manifests/kagent/assistant/secrets.yaml
```

> `secrets.yaml` захищено `.gitignore` — він не потрапить до репо.

### Структура Secret (приклад для lesson-credits / tasks)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mcp-lesson-credits-secrets
  namespace: kagent
type: Opaque
stringData:
  dot-env: |
    STORAGE_BACKEND=lakefs
    LAKEFS_ENDPOINT=http://<lakefs-host>:8001
    LAKEFS_ACCESS_KEY_ID=<access-key>
    LAKEFS_SECRET_ACCESS_KEY=<secret-key>
    LAKEFS_REPOSITORY=<repo-name>
    LAKEFS_BRANCH=main
```

## Крок 3 — Налаштувати KB_API_BASE_URL

Якщо knowledge-base backend знаходиться поза кластером — перевірте `KB_API_BASE_URL` у Secret `mcp-knowledge-base-secrets`:

```yaml
stringData:
  dot-env: |
    KB_API_BASE_URL=http://<service-ip-or-hostname>:8000
    API_KEY=<optional-api-key>
```

## Крок 5 — Застосувати маніфести

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

## Крок 6 — Перевірка

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

## Крок 7 — Відкрити kagent UI

Прямий доступ (Rancher Desktop):

```
http://192.168.64.4:8089/
```

Або через port-forward (якщо зовнішній IP недоступний):

```bash
kubectl -n kagent port-forward svc/kagent-ui 8089:8080
```

Браузер: **http://127.0.0.1:8089/** → оберіть **assistant-agent**.

> **Примітка:** Gateway слухає на порту `8089` (змінено з `80` через конфлікт із SSH-тунелем Rancher Desktop). Якщо після перезавантаження кластеру UI недоступний — дивіться розділ Troubleshooting нижче.

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

### kagent UI недоступний (`Unable to connect` / `404`)

Flux CD регулярно перезаписує Gateway назад на порт `80` (читає з OCI-артефакту, не з Git). Порт `80` конфліктує з SSH-тунелем Rancher Desktop — ServiceLB pod не може стартувати.

```bash
# Зупинити Flux від перезаписів
flux suspend kustomization releases

# Перевести Gateway на порт 8089
kubectl patch gateway agentgateway-external -n agentgateway-system \
  --type='json' -p='[{"op":"replace","path":"/spec/listeners/0/port","value":8089}]'

# Перезапустити проксі
kubectl rollout restart deployment agentgateway-external -n agentgateway-system

# Перевірка
curl -s -o /dev/null -w "%{http_code}" http://192.168.64.4:8089/
# Очікується: 200
```

> Після перезавантаження кластеру потрібно повторити ці 3 команди.

### Швидка діагностика

```bash
# Контролер kagent
kubectl logs -n kagent -l app.kubernetes.io/name=kagent-controller --tail=100

# Перезапустити под MCP після переробки образу
kubectl rollout restart deployment -n kagent -l app.kubernetes.io/name=mcp-lesson-credits
```

---

## Демонстрація роботи агента

Сесія після підключення MCP серверів до LakeFS (24 березня 2026).

### Запит балансу уроків

Агент викликає `lessons_list_calendars` та `lessons_get_balance`, отримує актуальні дані з lakeFS:

![Запит балансу](docs/screenshots/Screenshot%202026-03-24%20at%2022.39.00.png)

### Відповідь: баланс та пропозиція дій

Агент повертає поточний баланс (3 уроки) і пропонує варіанти:

![Відповідь агента](docs/screenshots/Screenshot%202026-03-24%20at%2022.39.07.png)

### Історія транзакцій

Запит `покажи історію платежів` — агент показує всі операції:

![Початок історії](docs/screenshots/Screenshot%202026-03-24%20at%2022.39.14.png)

### Поповнення балансу

Запит `поповни ще на 5 занять та покажи таблицю` — агент викликає `lessons_top_up`, баланс стає 8:

![Поповнення](docs/screenshots/Screenshot%202026-03-24%20at%2022.39.51.png)

### Таблиця транзакцій після поповнення

Повна таблиця: поповнення +12 у лютому, 9 списань і нове поповнення +5 сьогодні:

![Таблиця транзакцій](docs/screenshots/Screenshot%202026-03-24%20at%2022.40.00.png)

### Task Manager — список проєктів

Запит `покажи список поточних проєктів` — агент викликає `tasks_list_workspaces` і повертає workspaces з lakeFS:

![Список проєктів](docs/screenshots/Screenshot%202026-03-24%20at%2022.42.08.png)

---

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
