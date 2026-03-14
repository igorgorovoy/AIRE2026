# Lab1 — Medium: agentgateway + kagent у Kubernetes

Helm-деплой agentgateway в Kubernetes кластері з трьома LLM backends (Gemini, Anthropic, OpenAI) та інтеграцією kagent для AI-агентів.

## Структура

```
Lab1/medium/
├── run.sh                         # Єдиний скрипт деплою (кроки 1-8)
├── README.md
└── k8s/
    ├── agentgateway/
    │   ├── secret.yaml            # Secret: API ключі (llm-api-keys)
    │   ├── configmap.yaml         # ConfigMap: config.yaml для standalone-режиму
    │   └── gateway.yaml           # Gateway + AgentgatewayBackends + HTTPRoute
    └── kagent/
        ├── kagent-model.yaml      # ModelConfig: agentgateway → Gemini
        └── kagent-agent.yaml      # Agent: k8s-agentgateway-agent
```

## Передумови

| Інструмент | Встановлення |
|------------|-------------|
| `kubectl`  | https://kubernetes.io/docs/tasks/tools/ |
| `helm`     | https://helm.sh/docs/intro/install/ |
| `kagent`   | `brew install kagent` або [get-kagent script](https://kagent.dev/docs/kagent/getting-started/quickstart) |
| K8s кластер | [Rancher Desktop](https://rancherdesktop.io/) (k3s) — вже встановлено |

Rancher Desktop вже запущено (контекст `rancher-desktop`). Перевірте поточний контекст:
```bash
kubectl config current-context   # має бути rancher-desktop
kubectl cluster-info
```

## Швидкий старт

```bash
# 1. API ключі (мінімум — Gemini)
export GEMINI_API_KEY=your-gemini-key
export ANTHROPIC_API_KEY=your-anthropic-key   # опціонально
export OPENAI_API_KEY=your-openai-key         # опціонально

# 2. Запуск деплою
./run.sh
```

---

## Що робить `run.sh`

| Крок | Дія |
|------|-----|
| 0 | Перевірка `kubectl`, `helm`, `kagent`, підключення до кластера |
| 1 | Перевірка API ключів |
| 2 | Встановлення [Gateway API CRDs](https://gateway-api.sigs.k8s.io/) v1.4.0 |
| 3 | Helm install `agentgateway-crds` + `agentgateway` v2.2.1 |
| 4 | Kubernetes `Secret` `llm-api-keys` з API ключами |
| 5 | `Gateway` + `AgentgatewayBackend` (gemini/anthropic/openai) + `HTTPRoute` |
| 6 | `kagent install --profile demo` (вбудовані агенти) |
| 7 | `ModelConfig` (agentgateway→Gemini) + `Agent` (k8s-agentgateway-agent) |
| 8 | Виведення статусу та інструкцій |

---

## Архітектура

```
┌─────────────────────────────────────────────────────────────────┐
│  Kubernetes cluster                                             │
│                                                                 │
│  ┌──────────────┐    HTTPRoute     ┌─────────────────────────┐  │
│  │    kagent    │ ──────────────▶  │   agentgateway-proxy    │  │
│  │  (AI agents) │                  │   (Gateway API, :80)    │  │
│  └──────────────┘                  └───────────┬─────────────┘  │
│        │                                       │                │
│        │ ModelConfig                   x-provider header        │
│        ▼                               ┌───────┴───────┐        │
│  agentgateway-proxy                    ▼               ▼        │
│  (через svc URL)              ┌────────────┐  ┌──────────────┐  │
│                               │   gemini   │  │  anthropic   │  │
│                               │ (default)  │  │   openai     │  │
│                               └─────┬──────┘  └──────┬───────┘  │
└─────────────────────────────────────┼────────────────┼──────────┘
                                      ▼                ▼
                              Gemini API       Anthropic / OpenAI API
```

---

## Тести

### Port-forward для локального доступу

```bash
kubectl port-forward deployment/agentgateway-proxy \
  -n agentgateway-system 8080:8080
```

> **Примітка для Rancher Desktop (k3s):** порт 80 зайнятий Traefik (вбудований ingress-controller k3s). Gateway налаштовано на порт **8080**.

### Тест 1 — Gemini (за замовчуванням)

```bash
curl localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-2.5-flash",
    "messages": [{"role": "user", "content": "Привіт! Що таке Kubernetes?"}]
  }'
```

### Тест 2 — Anthropic (x-provider header)

```bash
curl localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "x-provider: anthropic" \
  -d '{
    "model": "claude-3-5-haiku-20241022",
    "messages": [{"role": "user", "content": "Привіт!"}]
  }'
```

### Тест 3 — OpenAI (x-provider header)

```bash
curl localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "x-provider: openai" \
  -d '{
    "model": "gpt-4.1-nano",
    "messages": [{"role": "user", "content": "Привіт!"}]
  }'
```

### Тест 4 — kagent dashboard

```bash
kagent dashboard
# Відкриється http://localhost:8082
```

### Тест 5 — kagent invoke (вбудований helm-agent)

```bash
# Список агентів
kagent get agent

# Запит до helm-agent
kagent invoke -t "What Helm charts are in my cluster?" --agent helm-agent

# Запит до власного агента через agentgateway
kagent invoke \
  -t "Які поди запущені в namespace agentgateway-system?" \
  --agent k8s-agentgateway-agent
```

### Перевірка ресурсів у кластері

```bash
# Всі ресурси agentgateway
kubectl get all -n agentgateway-system

# Backends та HTTPRoutes
kubectl get agentgatewaybackend -n agentgateway-system
kubectl get httproute -n agentgateway-system

# Gateway статус
kubectl get gateway agentgateway-proxy -n agentgateway-system

# kagent агенти
kubectl get agent -n kagent
kubectl get modelconfig -n kagent
```

---

## Secrets та ConfigMap

### Secret (llm-api-keys)

`run.sh` створює Secret безпосередньо з env-змінних:

```bash
kubectl create secret generic llm-api-keys \
  --namespace agentgateway-system \
  --from-literal=GEMINI_API_KEY="${GEMINI_API_KEY}" \
  --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  --from-literal=OPENAI_API_KEY="${OPENAI_API_KEY}"
```

> **Для production:** використовуйте [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets) або External Secrets Operator замість `stringData` у YAML файлах.

### ConfigMap (agentgateway-config)

`k8s/agentgateway/configmap.yaml` — конфіг у форматі standalone (для довідки). У Kubernetes-режимі agentgateway керується через `AgentgatewayBackend` CRD та `HTTPRoute` — конфіг генерується автоматично контролером.

---

## Очищення

```bash
# Видалити agentgateway
helm uninstall agentgateway agentgateway-crds -n agentgateway-system
kubectl delete namespace agentgateway-system

# Видалити kagent
kagent uninstall
kubectl delete namespace kagent

# Видалити kind кластер (якщо використовувався)
kind delete cluster
```

---

## Посилання

- [agentgateway Kubernetes Quickstart](https://agentgateway.dev/docs/kubernetes/latest/quickstart/install)
- [agentgateway LLM on K8s](https://agentgateway.dev/docs/kubernetes/latest/quickstart/llm)
- [kagent Quickstart](https://kagent.dev/docs/kagent/getting-started/quickstart)
- [Gateway API](https://gateway-api.sigs.k8s.io/)
- [Helm Charts agentgateway](https://agentgateway.dev/docs/kubernetes/latest/reference/helm)
