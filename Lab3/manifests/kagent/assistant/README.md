# Деплой Assistant Agent — Knowledge Base + Lesson Credits + Task Manager

Маніфести для **kagent**: 3 × `MCPServer` + 1 × `Agent`. Код Docker-образів: [`../../../mcp-servers/src/`](../../../mcp-servers/src/).

| Файл | Опис |
|------|------|
| `mcpserver-knowledge-base.yaml` | `MCPServer` `mcp-knowledge-base` |
| `mcpserver-lesson-credits.yaml` | `MCPServer` `mcp-lesson-credits` |
| `mcpserver-tasks.yaml` | `MCPServer` `mcp-tasks` |
| `agent.yaml` | `Agent` `assistant-agent` (посилається на 3 MCP-сервери) |
| `kustomization.yaml` | Kustomize: застосувати всі 4 ресурси |
| `all-in-one.yaml` | Всі 4 ресурси в одному файлі |

## Передумови

1. Кластер уже має **kagent** (namespace `kagent`, CRD `mcpservers`, `agents`).
2. Є **ModelConfig** `default-model-config`:

   ```bash
   kubectl get modelconfigs -n kagent
   ```

3. Налаштований **Secret** з `OPENAI_API_KEY` (або іншим провайдером).
4. Для `mcp-knowledge-base`: запущений KB backend і відомий його URL.

## 1. Зібрати Docker-образи

### mcp-knowledge-base (автономний)

```bash
# з кореня Lab3
docker build -t mcp-knowledge-base:latest mcp-servers/src/knowledge-base
```

### mcp-lesson-credits та mcp-tasks (потребують agentic-ai-landing-zone)

Обидва сервери мають залежності (`agents/`, `core/`) з проєкту `agentic-ai-landing-zone`.  
Збірка виконується **з кореня того проєкту** із вказівкою `-f` на Dockerfile.

```bash
ALZ=/path/to/agentic-ai-landing-zone
LAB3=/path/to/AIRE2026/Lab3

docker build -t mcp-lesson-credits:latest \
  -f "$LAB3/mcp-servers/src/lesson-credits/Dockerfile" "$ALZ"

docker build -t mcp-tasks:latest \
  -f "$LAB3/mcp-servers/src/tasks/Dockerfile" "$ALZ"
```

### Rancher Desktop / k3s (без реєстру)

Для Rancher Desktop образ, зібраний через `docker build`, як правило, видно Kubernetes.  
Якщо под у стані `ImagePullBackOff` — завантажте образ у VM вручну:

```bash
docker save mcp-knowledge-base:latest  -o ~/mcp-knowledge-base.tar
docker save mcp-lesson-credits:latest  -o ~/mcp-lesson-credits.tar
docker save mcp-tasks:latest           -o ~/mcp-tasks.tar

rdctl shell -- sh -lc 'sudo docker load -i ~/mcp-knowledge-base.tar'
rdctl shell -- sh -lc 'sudo docker load -i ~/mcp-lesson-credits.tar'
rdctl shell -- sh -lc 'sudo docker load -i ~/mcp-tasks.tar'
```

## 2. Налаштувати KB_API_BASE_URL

У `mcpserver-knowledge-base.yaml` (і `all-in-one.yaml`) замініть `KB_API_BASE_URL` на актуальний URL backend-сервісу:

```yaml
env:
  - name: KB_API_BASE_URL
    value: "http://<service>.<namespace>.svc.cluster.local:8000"
```

Якщо backend поза кластером — вкажіть зовнішній URL або IP.

## 3. Застосувати маніфести

З **кореня Lab3** — **один** із варіантів:

### Варіант A — один файл

```bash
kubectl apply -f manifests/kagent/assistant/all-in-one.yaml
```

### Варіант B — Kustomize

```bash
kubectl apply -k manifests/kagent/assistant
```

### Варіант C — по черзі (MCPServer → Agent)

```bash
kubectl apply -f manifests/kagent/assistant/mcpserver-knowledge-base.yaml
kubectl apply -f manifests/kagent/assistant/mcpserver-lesson-credits.yaml
kubectl apply -f manifests/kagent/assistant/mcpserver-tasks.yaml
kubectl apply -f manifests/kagent/assistant/agent.yaml
```

## 4. Перевірка

```bash
kubectl get mcpservers,agents -n kagent
kubectl get pods -n kagent | grep -E 'mcp-|NAME'

kubectl describe mcpserver mcp-knowledge-base -n kagent
kubectl describe mcpserver mcp-lesson-credits  -n kagent
kubectl describe mcpserver mcp-tasks           -n kagent
kubectl describe agent     assistant-agent     -n kagent
```

Очікується: всі поди у стані `Running`, агент `Ready` / `Accepted`.

## 5. Сервіси та доступ

### Зовнішній доступ (LoadBalancer)

| Сервіс | URL | Що це |
|--------|-----|-------|
| **kagent UI** | `http://192.168.64.4:8089/` | Веб-інтерфейс kagent |
| **kagent API** | `http://192.168.64.4:8089/api` | REST API kagent |
| **Traefik HTTP** | `http://192.168.64.4:80` | Ingress controller |
| **Traefik HTTPS** | `https://192.168.64.4:443` | Ingress controller |

> `192.168.64.4` — External IP Rancher Desktop. Уточнити: `kubectl get svc -n agentgateway-system agentgateway-external`

### Агенти (ClusterIP, namespace `kagent`)

| Сервіс | Port | Опис |
|--------|------|------|
| `assistant-agent` | 8080 | Наш агент (Lab3) |
| `k8s-agent` | 8080 | Kubernetes агент |
| `observability-agent` | 8080 | Observability агент |
| `promql-agent` | 8080 | PromQL агент |
| `helm-agent` | 8080 | Helm агент |
| `kagent-grafana-mcp` | 8000 | Grafana MCP |

### MCP-сервери (namespace `kagent`)

| Сервіс | Port | Опис |
|--------|------|------|
| `mcp-knowledge-base` | 3000 | Knowledge Base (Lab3) |
| `mcp-lesson-credits` | 3000 | Lesson Credits (Lab3) |
| `mcp-tasks` | 3000 | Task Manager (Lab3) |

### Відкрити kagent UI

Прямий доступ (Rancher Desktop):
```
http://192.168.64.4:8089/
```

Або через port-forward (якщо External IP недоступний):
```bash
kubectl -n agentgateway-system port-forward svc/agentgateway-external 8089:8089
```
Браузер: **http://127.0.0.1:8089/** → оберіть агента **assistant-agent**.

Приклади запитів:
- *«Скільки уроків залишилось у English. Mary?»*
- *«Покажи список відкритих карток на дошці X»*
- *«Знайди документ про AWS у knowledge base»*

## 6. Видалити (за потреби)

```bash
kubectl delete -f manifests/kagent/assistant/all-in-one.yaml
# або
kubectl delete -k manifests/kagent/assistant
```

## Troubleshooting

### `Failed to create MCP session` / `TaskGroup` у UI

1. Перевір, чи всі MCPServer поди у `Running`:
   ```bash
   kubectl get pods -n kagent | grep mcp
   kubectl logs -n kagent -l app.kubernetes.io/name=mcp-lesson-credits --tail=50
   ```
2. Перевір контролер:
   ```bash
   kubectl logs -n kagent -l app.kubernetes.io/name=kagent-controller --tail=100
   ```
3. Ім'я інструменту в `toolNames` має точно збігатися з назвою в `server.py` (`@mcp.tool()`).

### `ImagePullBackOff`

- Переконайтесь, що `imagePullPolicy: IfNotPresent` задано.
- Для k3s/Rancher Desktop: завантажте образ через `docker save` + `rdctl shell` (див. розділ 1).

### `ModuleNotFoundError: agents` або `core`

- Образ `mcp-lesson-credits` / `mcp-tasks` зібрано не з кореня `agentic-ai-landing-zone`.
- Перевірте, що аргумент `-f` вказує на правильний Dockerfile, а контекст збірки — корінь ALZ.

### Дані зникають після рестарту поду

- За замовчуванням `STORAGE_BACKEND=local` → дані в `emptyDir` всередині контейнера.
- Для persistence: змонтуйте `PersistentVolumeClaim` або переключіть на lakeFS.

### `Unable to connect` / Gateway повертає 404

**Симптом:** браузер не може відкрити `http://192.168.64.4:8089/`, або Gateway відповідає `404 route not found`.

**Причина:** Flux CD керує Gateway через OCI-артефакт (`oci://ghcr.io/den-vasyliev/abox/releases`), а не через Git-файл. Після кожної Flux-синхронізації порт Gateway повертається на `80`, а ServiceLB pod (`svclb-agentgateway-external`) не може стартувати, бо порт 80 зайнятий SSH-тунелем Rancher Desktop.

**Діагностика:**

```bash
# Перевірити поточний порт Gateway і ServiceLB pod
kubectl get gateway agentgateway-external -n agentgateway-system \
  -o jsonpath='{.spec.listeners[0].port}'
kubectl get pods -n kube-system | grep svclb-agentgateway
```

**Виправлення:**

```bash
# 1. Зупинити Flux від перезапису Gateway
flux suspend kustomization releases

# 2. Перевести Gateway на порт 8089
kubectl patch gateway agentgateway-external -n agentgateway-system \
  --type='json' -p='[{"op":"replace","path":"/spec/listeners/0/port","value":8089}]'

# 3. Перезапустити проксі (щоб перечитав XDS-маршрути)
kubectl rollout restart deployment agentgateway-external -n agentgateway-system
kubectl rollout status deployment agentgateway-external -n agentgateway-system
```

> **Після перезавантаження кластеру** Flux знову відновиться — повторіть кроки 1–3.

**Перевірка:**

```bash
curl -s -o /dev/null -w "%{http_code}" http://192.168.64.4:8089/
# Має повернути: 200
```

**Альтернатива без маніпуляцій з Flux** — port-forward напряму на UI:

```bash
kubectl -n kagent port-forward svc/kagent-ui 8089:8080
# Браузер: http://127.0.0.1:8089/
```
