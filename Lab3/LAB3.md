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

> **Передумова:** переконайтесь що Docker запущено та доступний з командного рядка (`docker info`). Для Rancher Desktop достатньо щоб застосунок був відкритий.

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

MCP-сервери отримують конфігурацію через механізм `secretRefs` у kagent. Кожен ключ Secret стає окремою змінною середовища у контейнері (тому кожна змінна — окремий ключ у `stringData`).

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

### Структура Secret

> **Важливо:** kagent інжектує кожен ключ Secret як окрему env var. Використовуйте **один ключ = одна змінна** (не multiline `dot-env`).

Приклад для lesson-credits / tasks:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mcp-lesson-credits-secrets
  namespace: kagent
type: Opaque
stringData:
  STORAGE_BACKEND: "lakefs"
  LAKEFS_ENDPOINT: "http://<lakefs-host>:8001"
  LAKEFS_ACCESS_KEY_ID: "<access-key>"        # замініть на реальний ключ
  LAKEFS_SECRET_ACCESS_KEY: "<secret-key>"    # замініть на реальний ключ
  LAKEFS_REPOSITORY: "<repo-name>"
  LAKEFS_BRANCH: "main"
```

Приклад для knowledge-base:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mcp-knowledge-base-secrets
  namespace: kagent
type: Opaque
stringData:
  KB_API_BASE_URL: "http://<service-ip-or-hostname>:8000"
  API_KEY: "<optional-api-key>"               # замініть на реальний ключ
```

> Готовий шаблон: `manifests/kagent/assistant/secrets-example.yaml`. Скопіюйте у `secrets.yaml` і замініть `<...>` на реальні значення. Файл захищено `.gitignore`.

## Крок 3 — Налаштувати KB_API_BASE_URL

Якщо knowledge-base backend знаходиться поза кластером — перевірте `KB_API_BASE_URL` у Secret `mcp-knowledge-base-secrets` (приклад структури у розділі вище).

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

## Крок 6 — Перевірка деплойменту

### 6.1 Загальний стан ресурсів

```bash
kubectl get mcpservers,agents -n kagent
kubectl get pods -n kagent | grep -E 'mcp-|NAME'
```

Очікується: поди у стані `Running`, агент `Ready` / `Accepted`.

### 6.2 Перевірка env vars у подах (storage backend)

Критично переконатись що секрети правильно інжектовано і `STORAGE_BACKEND=lakefs`:

```bash
# Перевірте кожен MCP-сервер
for svc in mcp-knowledge-base mcp-lesson-credits mcp-tasks; do
  POD=$(kubectl get pod -n kagent -l app.kubernetes.io/name=$svc -o name | head -1)
  echo "=== $svc ==="
  kubectl exec -n kagent "$POD" -- env | grep -E 'STORAGE|LAKEFS|KB_API|ENABLE_DELETE'
done
```

Очікуваний вивід для lesson-credits / tasks:
```
STORAGE_BACKEND=lakefs
LAKEFS_ENDPOINT=http://...
LAKEFS_ACCESS_KEY_ID=...
ENABLE_DELETE_TOOLS=0
```

### 6.3 Логи та деталі

```bash
# Деталі CRD
kubectl describe mcpserver mcp-knowledge-base -n kagent
kubectl describe mcpserver mcp-lesson-credits  -n kagent
kubectl describe mcpserver mcp-tasks           -n kagent
kubectl describe agent     assistant-agent     -n kagent

# Логи MCP-серверів
kubectl logs -n kagent -l app.kubernetes.io/name=mcp-knowledge-base  --tail=30
kubectl logs -n kagent -l app.kubernetes.io/name=mcp-lesson-credits  --tail=30
kubectl logs -n kagent -l app.kubernetes.io/name=mcp-tasks           --tail=30
```

### 6.4 Функціональна перевірка через UI

Після переходу в kagent UI → assistant-agent виконайте тестові запити:

| Сервер | Тестовий запит | Очікуваний результат |
|--------|---------------|---------------------|
| knowledge-base | "Скільки документів у базі знань?" | Число документів з LakeFS/backend |
| lesson-credits | "Скільки уроків залишилось?" | Баланс з LakeFS |
| tasks | "Покажи всі workspaces" | Список воркспейсів |

Якщо відповіді відповідають реальним даним — деплоймент успішний.

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

> **Примітка щодо порту 8089:** Gateway налаштовано на порту `8089` замість стандартного `80`. Причина: порт `80` конфліктує з SSH-тунелем Rancher Desktop — pod `svclb-agentgateway-external` не стартує через `EADDRINUSE`. Якщо після перезавантаження кластеру UI недоступний — Flux CD міг повернути конфігурацію назад; дивіться розділ Troubleshooting → "kagent UI недоступний".

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

### MCP-сервер запустився, але повертає порожні дані / "local storage"

Симптом: агент звертається до MCP, але дані не відповідають тому що видно у веб-інтерфейсі сховища.

Причина: `STORAGE_BACKEND=local` з Dockerfile перекриває значення з Secret, якщо Secret застосовано неправильно.

```bash
# 1. Перевірте що Secret існує і містить правильні ключі
kubectl get secret mcp-lesson-credits-secrets -n kagent -o yaml

# 2. Перевірте env vars у живому поді (має бути STORAGE_BACKEND=lakefs)
POD=$(kubectl get pod -n kagent -l app.kubernetes.io/name=mcp-lesson-credits -o name | head -1)
kubectl exec -n kagent "$POD" -- env | grep STORAGE

# 3. Якщо STORAGE_BACKEND=local — видаліть і перестворіть Secret з окремими ключами
kubectl delete secret mcp-lesson-credits-secrets -n kagent
kubectl apply -f manifests/kagent/assistant/secrets.yaml

# 4. Перезапустіть деплоймент
kubectl rollout restart deployment -n kagent -l app.kubernetes.io/name=mcp-lesson-credits
```

### Сервіс недоступний / под у стані CrashLoopBackOff

```bash
# Подивитись events пода
kubectl describe pod -n kagent -l app.kubernetes.io/name=mcp-lesson-credits

# Останні логи до краш-ресету
kubectl logs -n kagent -l app.kubernetes.io/name=mcp-lesson-credits --previous --tail=50
```

Типові причини:
- Неправильний `image:` tag — образ не знайдено (`ErrImagePull`)
- Відсутній Secret — `secretRef` посилається на неіснуючий ресурс
- Port 80 conflict (ServiceLB) — дивіться розділ "kagent UI недоступний"

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

### Стан кластера (k9s)

Всі 31 поди у `Running`, три MCP сервери (`mcp-lesson-credits`, `mcp-tasks`, `mcp-knowledge-base`) запущені з 0 рестартів — lakeFS підключено коректно:

![k9s cluster state](docs/screenshots/Screenshot%202026-03-24%20at%2022.45.23.png)

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


### ModuleNotFoundError: agents / core

Образ зібрано не з кореня `agentic-ai-landing-zone`. Переконайтесь:
```bash
# Перевірка правильного контексту збірки
docker build -t mcp-lesson-credits:latest \
  -f "$LAB3/mcp-servers/src/lesson-credits/Dockerfile" \
  "$ALZ"   # ← контекст = корінь ALZ
```
