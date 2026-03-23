# Лабораторна: #2 (Rancher Desktop + abox)

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

Загальні варіанти: готовий пакет через `uvx` / `npx` ([приклад із `mcp-server-fetch`](https://kagent.dev/docs/kagent/getting-started/first-mcp-tool)) або **власний образ** з FastMCP ([kmcp: deploy server](https://kagent.dev/docs/kmcp/deploy/server)).

#### Приклад для лабораторної: MCP «скласти два числа»

У репозиторії є:

- код і Dockerfile: [`docs/examples/add-two-mcp/`](../examples/add-two-mcp/) — інструмент **`add_two_numbers(a, b)`** на Python (FastMCP);
- **канонічні маніфести** та покроковий деплой: [`manifests/kagent/add-two-mcp/README.md`](../manifests/kagent/add-two-mcp/README.md).

Файли в `manifests/kagent/add-two-mcp/`:

| Файл | Призначення |
|------|-------------|
| `all-in-one.yaml` | `MCPServer` + `Agent` одним `kubectl apply` |
| `mcpserver.yaml` / `agent.yaml` | окремо, якщо потрібен поетапний деплой |
| `kustomization.yaml` | `kubectl apply -k manifests/kagent/add-two-mcp` |

1. Зібрати образ (з **кореня Lab2**):

   ```bash
   docker build -t add-two-mcp:latest docs/examples/add-two-mcp
   ```

   **Rancher Desktop без registry:** якщо після `kubectl apply` под MCP у `ImagePullBackOff`, завантаж образ у VM через `rdctl` (повна послідовність у [`manifests/kagent/add-two-mcp/README.md`](../manifests/kagent/add-two-mcp/README.md), підрозділ «Без Docker registry»):

   ```bash
   docker save add-two-mcp:latest -o "$HOME/add-two-mcp.tar"
   rdctl shell -- sh -lc 'sudo docker load -i '"$HOME"'/add-two-mcp.tar'
   kubectl delete pod -n kagent -l app.kubernetes.io/name=mcp-add-two
   kubectl get pods -n kagent | grep mcp-add-two
   ```

2. Застосувати маніфести (див. повну інструкцію в README каталогу маніфестів):

   ```bash
   kubectl apply -f manifests/kagent/add-two-mcp/all-in-one.yaml
   ```

   Або одним файлом через симлінк (те саме): [`docs/examples/add-two-mcp/k8s.yaml`](../examples/add-two-mcp/k8s.yaml) → `all-in-one.yaml`.

   Фрагмент **`MCPServer`** (ім’я інструменту має збігатися з `server.py` — тут `add_two_numbers`):

   ```yaml
   apiVersion: kagent.dev/v1alpha1
   kind: MCPServer
   metadata:
     name: mcp-add-two
     namespace: kagent
   spec:
     deployment:
       image: add-two-mcp:latest
       imagePullPolicy: IfNotPresent
       port: 3000
       cmd: python
       args:
         - /app/server.py
     stdioTransport: {}
     transportType: stdio
   ```

3. Перевірка:

   ```bash
   kubectl get mcpservers -n kagent
   kubectl get pods -n kagent | grep -i add-two
   ```

   `apiVersion` для `MCPServer`/`Agent` підлаштуй під `kubectl explain mcpserver` / `kubectl explain agent`, якщо кластер на іншій версії CRD.

### 3.3 Декларативний агент

Створи **`Agent`** з `spec.type: Declarative`, посиланням на `modelConfig` і `tools` → твій **`MCPServer`** з переліком `toolNames`.

#### Приклад: агент «скласти два числа»

Агент використовує той самий `MCPServer` `mcp-add-two` і лише інструмент `add_two_numbers`:

```yaml
apiVersion: kagent.dev/v1alpha2
kind: Agent
metadata:
  name: add-numbers-agent
  namespace: kagent
spec:
  description: Агент, який складає два числа через MCP-інструмент add_two_numbers.
  type: Declarative
  declarative:
    modelConfig: default-model-config
    systemMessage: |
      Ти допоміжний асистент. У тебе є інструмент add_two_numbers(a, b) — сума двох цілих чисел.
      Коли користувач просить додати, скласти або підсумувати два числа, викликай цей інструмент з відповідними a та b.
      Якщо числа не вказані чітко — уточни. Відповідай у Markdown і коротко поясни результат.
    tools:
      - type: McpServer
        mcpServer:
          apiGroup: kagent.dev
          name: mcp-add-two
          kind: MCPServer
          toolNames:
            - add_two_numbers
```

Застосування (поточний каталог — корінь **Lab2**):

```bash
kubectl apply -f manifests/kagent/add-two-mcp/all-in-one.yaml
```

(Еквівалентно: `kubectl apply -f docs/examples/add-two-mcp/k8s.yaml` — симлінк на той самий файл.)

Перевірка:

```bash
kubectl get agents -n kagent
kubectl describe agent add-numbers-agent -n kagent
```

Чат у UI — після port-forward на порт **8080** (див. вище); вибери агента **add-numbers-agent** і спробуй запит на кшталт: *«Склади 17 і 25»*.

Додатково: [Use MCP servers and tools in kagent](https://kagent.dev/docs/kagent/getting-started/first-mcp-tool).

---

## Скріншоти

Знімки лежать у каталозі репозиторію **`images/lab/`** (оригінали можна зберегти з macOS у `~/Movies/Screenshot … .png` і скопіювати сюди).

### Успішний результат (kagent + MCP `add_two_numbers`)

Після налаштування моделі, Secret з `OPENAI_API_KEY`, деплою `mcp-add-two` та агента `add-numbers-agent` очікується така поведінка:

1. **kagent UI** — запит *«склади 8 та 77»*, виклик інструмента `add_two_numbers` з `a: 8`, `b: 77`, результат **85** і текстова відповідь агента.

   ![kagent: успішний виклик add_two_numbers (8 + 77 = 85)](images/lab/screenshot-success-160403.png)

2. **kagent UI** — кілька успішних діалогів (у т.ч. додатковий приклад з від’ємним числом).

   ![kagent: кілька успішних запитів до add-numbers-agent](images/lab/screenshot-success-160445.png)

3. **k9s** — поди в namespace `kagent` у стані `Running` / `Ready`, зокрема `mcp-add-two` та `add-numbers-agent`.

   ![k9s: поди kagent (mcp-add-two, add-numbers-agent)](images/lab/screenshot-success-160451.png)

---

### Інші кроки лабораторної

1. ![Скріншот 2](images/lab/screenshot-120856.png)
2. ![Скріншот 3](images/lab/screenshot-121048.png)
3. ![Скріншот 4](images/lab/screenshot-121315.png)


4. ![Скріншот 7](images/lab/screenshot-122350.png)

5. ![Скріншот 9](images/lab/screenshot-125000.png)
6. ![Скріншот 10](images/lab/screenshot-125010.png)
7. ![Скріншот 11](images/lab/screenshot-131531.png)
8. ![Скріншот 12](images/lab/screenshot-131538.png)

---

## Корисні посилання

- [kagent — перший MCP tool](https://kagent.dev/docs/kagent/getting-started/first-mcp-tool)
- [abox README](../README.md) — bootstrap, Flux, troubleshooting
