# Деплой MCP «скласти два числа» + агент `add-numbers-agent`

Маніфести для **kagent**: `MCPServer` + `Agent`. Код Docker-образа: [`../../docs/examples/add-two-mcp/`](../../docs/examples/add-two-mcp/).

| Файл | Опис |
|------|------|
| `mcpserver.yaml` | Лише `MCPServer` `mcp-add-two` |
| `agent.yaml` | Лише `Agent` `add-numbers-agent` |
| `kustomization.yaml` | Kustomize: застосувати обидва ресурси |
| `all-in-one.yaml` | Обидва ресурси в одному файлі |

## Передумови

1. Кластер уже має **kagent** (namespace `kagent`, CRD `mcpservers`, `agents`).
2. Є **ModelConfig** (типово `default-model-config`):

   ```bash
   kubectl get modelconfigs -n kagent
   ```

3. Налаштовано **Secret** з `OPENAI_API_KEY` для провайдера (див. [`LAB2.md`](../../LAB2.md), розділ про модель / OpenAI).

## 1. Зібрати Docker-образ

З **кореня репозиторію Lab2** (де лежать `manifests/` і `docs/`):

```bash
docker build -t add-two-mcp:latest docs/examples/add-two-mcp
```

### Rancher Desktop

Зазвичай образ, зібраний через **Docker / `docker build`**, доступний Kubernetes того ж Rancher Desktop (спільний image store). Якщо под у стані `ImagePullBackOff` / `ErrImageNeverPull`:

- У **Rancher Desktop → Kubernetes** увімкни використання той самий container runtime, що й Docker (або завантаж образ у registry, доступний кластеру).
- Альтернатива: запушити образ у GHCR/Docker Hub і в `mcpserver.yaml` замінити `image: add-two-mcp:latest` на повний шлях, напр. `ghcr.io/<user>/add-two-mcp:latest`.

#### Без Docker registry (імпорт у VM Rancher Desktop)

Якщо kubelet тягне образ з Docker Hub (`pull access denied for add-two-mcp`), а локальний build не видно ноді — збережи образ у tar і завантаж його в **Docker daemon всередині VM** Rancher Desktop через `rdctl shell` (той самий store, який використовує Kubernetes):

```bash
# з кореня Lab2
docker build -t add-two-mcp:latest docs/examples/add-two-mcp
docker save add-two-mcp:latest -o "$HOME/add-two-mcp.tar"

rdctl shell -- sh -lc 'sudo docker load -i '"$HOME"'/add-two-mcp.tar'

kubectl delete pod -n kagent -l app.kubernetes.io/name=mcp-add-two
kubectl get pods -n kagent | grep mcp-add-two
```

На macOS шлях `$HOME/add-two-mcp.tar` зазвичай доступний у `rdctl shell` під тим самим шляхом. Якщо `load` не знаходить файл — збережи tar у каталог, який точно змонтований у VM, або скопіюй файл у VM вручну.

## 2. Застосувати маніфести

Перейди в корінь **Lab2** і виконай **один** із варіантів.

### Варіант A — один файл

```bash
kubectl apply -f manifests/kagent/add-two-mcp/all-in-one.yaml
```

### Варіант B — Kustomize (два файли)

```bash
kubectl apply -k manifests/kagent/add-two-mcp
```

### Варіант C — по черзі

```bash
kubectl apply -f manifests/kagent/add-two-mcp/mcpserver.yaml
kubectl apply -f manifests/kagent/add-two-mcp/agent.yaml
```

## 3. Перевірка

```bash
kubectl get mcpservers,agents -n kagent
kubectl get pods -n kagent | grep -E 'add-two|mcp-add|NAME'
kubectl describe mcpserver mcp-add-two -n kagent
kubectl describe agent add-numbers-agent -n kagent
```

Очікується: поди MCP у `Running`, агент у статусі **Ready** / **Accepted** (залежно від версії CRD).

## 4. Відкрити kagent UI

```bash
kubectl -n agentgateway-system port-forward svc/agentgateway-external 8080:80
```

Браузер: **http://127.0.0.1:8080/** → обери агента **add-numbers-agent**, перевір чат (*«Склади 17 і 25»*).

### Приклад успішного результату

У [`LAB2.md`](../../LAB2.md) (розділ **«Успішний результат»**) є скріншоти: виклик MCP `add_two_numbers`, відповідь у чаті та перевірка подів у k9s — файли в [`images/lab/`](../../images/lab/).

## 5. Видалити (за потреби)

```bash
kubectl delete -f manifests/kagent/add-two-mcp/all-in-one.yaml
# або
kubectl delete -k manifests/kagent/add-two-mcp
```

## Troubleshooting

### `Failed to create MCP session` / `TaskGroup` у UI

1. У блоці `spec.declarative.tools[].mcpServer` має бути повне посилання на CRD, зокрема **`apiGroup: kagent.dev`** поруч із `kind: MCPServer` та `name` (див. [troubleshooting kagent](https://github.com/kagent-dev/kagent/blob/main/docs/troubleshooting.md)).
2. Перевір поди MCP та контролер:

   ```bash
   kubectl get pods,mcpserver,agent -n kagent
   kubectl logs -n kagent -l app.kubernetes.io/name=kagent-controller --tail=100
   kubectl describe mcpserver mcp-add-two -n kagent
   ```

3. Якщо под MCP у **CrashLoop** / **ImagePullBackOff**:
   - У маніфесті вже задано **`imagePullPolicy: IfNotPresent`**: для тега `:latest` Kubernetes інакше використовує **`Always`** і намагається стягнути неіснуючий образ з Docker Hub.
   - Перезбери образ `add-two-mcp:latest` і переконайся, що **Rancher Desktop / k3s** бачить той самий image store, що й `docker build` (див. розділ «1. Зібрати Docker-образ»). Якщо образу все ще немає на ноді — спробуй тег без `latest`, напр. `add-two-mcp:local`, або `imagePullPolicy: Never` лише після того, як образ гарантовано завантажений у runtime кластера.
   - На **Rancher Desktop** без registry: див. підрозділ **«Без Docker registry (імпорт у VM Rancher Desktop)»** вище (`docker save` → `rdctl shell` → `sudo docker load`).

## Примітки

- Якщо `kubectl explain mcpserver` показує інший `apiVersion` — підлаштуй поля в YAML під свій кластер.
- Ім’я інструменту в `toolNames` має збігатися з реєстрацією у `server.py` (`add_two_numbers`).
