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

3. Налаштовано **Secret** з `OPENAI_API_KEY` для провайдера (див. [`docs/LAB_BEGINNER.md`](../../docs/LAB_BEGINNER.md), розділ 3.1).

## 1. Зібрати Docker-образ

З **кореня репозиторію Lab2** (де лежать `manifests/` і `docs/`):

```bash
docker build -t add-two-mcp:latest docs/examples/add-two-mcp
```

### Rancher Desktop

Зазвичай образ, зібраний через **Docker / `docker build`**, доступний Kubernetes того ж Rancher Desktop (спільний image store). Якщо под у стані `ImagePullBackOff` / `ErrImageNeverPull`:

- У **Rancher Desktop → Kubernetes** увімкни використання той самий container runtime, що й Docker (або завантаж образ у registry, доступний кластеру).
- Альтернатива: запушити образ у GHCR/Docker Hub і в `mcpserver.yaml` замінити `image: add-two-mcp:latest` на повний шлях, напр. `ghcr.io/<user>/add-two-mcp:latest`.

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

## 5. Видалити (за потреби)

```bash
kubectl delete -f manifests/kagent/add-two-mcp/all-in-one.yaml
# або
kubectl delete -k manifests/kagent/add-two-mcp
```

## Примітки

- Якщо `kubectl explain mcpserver` показує інший `apiVersion` — підлаштуй поля в YAML під свій кластер.
- Ім’я інструменту в `toolNames` має збігатися з реєстрацією у `server.py` (`add_two_numbers`).
