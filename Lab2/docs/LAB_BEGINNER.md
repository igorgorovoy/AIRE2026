# Лабораторна: початковий рівень (Rancher Desktop + abox)

Цей документ покриває пункти **2–3** для треку **початківців**, після успішного `make run` / `tofu apply` і `READY` у Flux.

---

## 2. Доступ до Flux, kagent UI та agentgateway

### Flux (стан GitOps)

#### Веб-інтерфейс: Flux Status Web UI (Flux Operator)

**Control Plane Flux Operator** уже містить веб-інтерфейс **Flux Status** (огляд GitOps / стану Flux). За замовчуванням він слухає порт **9080** у поді оператора.

Перевір сервіс (ім’я може збігатися з релізом `flux-operator`):

```bash
kubectl get svc -n flux-system
```

Типовий доступ з ноутбука (Rancher Desktop):

```bash
kubectl -n flux-system port-forward svc/flux-operator 9080:9080
```

Відкрий у браузері: **http://127.0.0.1:9080/**

Якщо `svc/flux-operator` не знайдено, подивись точне ім’я:

```bash
kubectl get svc -n flux-system -l app.kubernetes.io/name=flux-operator
# або
kubectl get pods -n flux-system -l app.kubernetes.io/name=flux-operator -o wide
```

Окремий деплой **лише** UI (без повторного оператора) — за потреби з другого Helm release, див. [flux-operator chart: `web.serverOnly`](https://artifacthub.io/packages/helm/flux-operator/flux-operator).

#### CLI та kubectl (без браузера)

| Що | Як відкрити |
|----|-------------|
| Огляд ресурсів | `bash scripts/flux.sh get all` або `flux get all` (після [налаштування flux у zsh](../README.md#troubleshooting)) |
| Інтерактивно | `k9s -n flux-system` (якщо встановлено) |
| Події / деталі | `kubectl get kustomization,helmrelease,ocirepository -n flux-system` |

Метрики source-controller (не UI):

```bash
kubectl -n flux-system port-forward svc/source-controller 9090:9090
# http://127.0.0.1:9090/metrics
```

### Kagent UI + agentgateway (одна точка входу)

Трафік іде через **Gateway** `agentgateway-external` і **HTTPRoute** `kagent` (`/` → UI `:8080`, `/api` → controller `:8083`).

На Rancher Desktop **LoadBalancer** часто лишається `<pending>`. Найстабільніший доступ:

```bash
kubectl -n agentgateway-system port-forward svc/agentgateway-external 8080:80
```

Відкрий у браузері: **http://127.0.0.1:8080/** — це **kagent UI** через agentgateway.

Альтернатива (якщо NodePort доступний з хоста):

```bash
kubectl get svc -n agentgateway-system agentgateway-external
# спробуй curl до NodePort на 80, напр. http://127.0.0.1:<nodePort>/
```

CLI-дашборд від kagent (якщо встановлено `kagent` локально):

```bash
kagent dashboard
```

(див. [документацію kagent](https://kagent.dev/docs/kagent/getting-started/first-mcp-tool).)

**agentgateway** як компонент — це контролер + той самий Gateway; окремого “адмін-UI” у мінімальному HelmRelease немає: діагностика через `kubectl get gateway,httproute -A` і логи подів у `agentgateway-system`.

---

## 3. Модель, декларативний MCP tool server та агент

### 3.1 Підключити модель (OpenAI за замовчуванням)

У `releases/kagent.yaml` задано провайдер `openAI` і ключ **`OPENAI_API_KEY`**. Створи Secret у namespace `kagent` (ім’я залежить від Helm chart; перевір після встановлення):

```bash
kubectl get helmrelease kagent -n kagent -o yaml | grep -i secret
kubectl get pods,secret -n kagent
```

Типовий варіант — secret з ключем `OPENAI_API_KEY`:

```bash
kubectl create secret generic kagent-provider-openai -n kagent \
  --from-literal=OPENAI_API_KEY="sk-..." \
  --dry-run=client -o yaml | kubectl apply -f -
```

Якщо реліз очікує **інше** ім’я Secret — подивись values у HelmRelease або документацію чарту kagent `0.7.23` і підстав відповідне ім’я в `kubectl patch` / `HelmRelease.values`.

Переконайся, що є **ModelConfig** (часто `default-model-config` з прикладів kagent):

```bash
kubectl get modelconfigs -n kagent
```

Детальніше: [Your First Agent](https://kagent.dev/docs/kagent/getting-started/first-agent).

### 3.2 Декларативний MCP server

Створи ресурс **`MCPServer`** (`kagent.dev/v1alpha1` або актуальна версія в кластері):

```bash
kubectl api-resources | grep -i mcp
```

Приклад (узятий з офіційного гайду — адаптуй `apiVersion` під свій кластер):

- [Use MCP servers and tools in kagent](https://kagent.dev/docs/kagent/getting-started/first-mcp-tool)

Мінімальна ідея: `MCPServer` з `uvx` + `stdio` transport, потім перевірка подів у `kagent`.

### 3.3 Декларативний агент

Створи **`Agent`** з `spec.type: Declarative`, посиланням на `modelConfig` і `tools` → твій `MCPServer`:

- [Той самий гайд — секція Creating an agent](https://kagent.dev/docs/kagent/getting-started/first-mcp-tool)

Перевірка:

```bash
kubectl get agents -n kagent
kubectl describe agent <name> -n kagent
```

Чат у UI — після port-forward на порт **8080** (див. вище).

---

## Скрінкаст (умова: лише трек для початківців)

Якщо виконуєш **тільки** завдання початкового рівня (цей документ + базовий сценарій без додаткових задач “просунутий рівень”):

1. Запиши сесію терміналу, наприклад:

   ```bash
   asciinema rec docs/screencasts/lab2-beginner.cast
   ```

2. Завантаж на asciinema.org або додай **посилання** у PR/README поруч із позначкою `beginner`.

3. Великі файли `.cast` краще **не** комітити в git — залиш посилання; якщо комітиш файл, тримай розмір розумним або додай `docs/screencasts/*.cast` у `.gitignore` локально.

Якщо лаба включає **просунуті** пункти — скрінкаст у репозиторії **не обов’язковий** (достатньо логів / скріншотів за вимогами викладача).

---

## Корисні посилання

- [kagent — перший MCP tool](https://kagent.dev/docs/kagent/getting-started/first-mcp-tool)
- [abox README](../README.md) — bootstrap, Flux, troubleshooting
