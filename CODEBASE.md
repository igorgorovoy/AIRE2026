# CODEBASE.md — AI Review Context

> Цей файл надає AI-рев'юверу контекст про репозиторій AIRE2026.
> Оновлюй при додаванні нових компонентів або зміні архітектури.

## Мета проекту

**AIRE2026** — навчальний репозиторій курсу AI & Reliability Engineering 2026.
Демонструє побудову AI-агентів та LLM-gateway на базі [agentgateway](https://agentgateway.dev) та [kagent](https://kagent.dev).

## Структура

```
AIRE2026/
├── Lab1/
│   ├── beginers/          # Standalone: agentgateway бінар + config.yaml
│   │   ├── run.sh         # Bash: інсталяція + запуск
│   │   └── config.yaml    # agentgateway конфіг (YAML)
│   ├── medium/            # Kubernetes: Helm + kagent
│   │   ├── run.sh         # Bash: Helm install + kubectl apply
│   │   ├── k8s/
│   │   │   ├── agentgateway/  # Gateway, Backends, HTTPRoute маніфести
│   │   │   ├── kagent/        # ModelConfig, Agent маніфести
│   │   │   └── ingress.yaml   # Traefik Ingress
│   │   └── screenshots/   # Документаційні скріншоти
│   └── max/               # Advanced (в розробці)
├── .github/
│   ├── workflows/         # GitHub Actions
│   └── scripts/           # Python-скрипти для workflows
├── CODEBASE.md            # Цей файл
├── REVIEW.md              # AI-рев'ю критерії
└── EVALS.md               # Методологія оцінки рев'ю
```

## Технологічний стек

| Компонент | Технологія | Версія |
|-----------|------------|--------|
| LLM Gateway | agentgateway | v1.0.0-rc.2 (standalone), v2.2.1 (k8s) |
| AI Agents | kagent | v0.7.23 |
| Kubernetes | k3s (Rancher Desktop) | v1.x |
| Helm | Helm | v3.x |
| Ingress | Traefik | v3.x |
| CI/CD | GitHub Actions | — |
| AI Review | GitHub Models | gpt-4o-mini |

## Ключові файли та їх призначення

### `Lab1/beginers/config.yaml`
- YAML конфіг для agentgateway standalone
- Визначає `binds`, `listeners`, `routes`, `backends`, `policies`
- Підтримує змінні середовища через `$VAR_NAME` синтаксис
- Схема: `https://agentgateway.dev/schema/config`

### `Lab1/beginers/run.sh`
- Bash-скрипт з `set -e` (fail-fast)
- Завантажує бінар agentgateway з GitHub Releases
- Перевіряє наявність API ключів перед запуском
- Підтримує darwin/linux, arm64/amd64

### `Lab1/medium/run.sh`
- Bash-скрипт з `set -euo pipefail` (суворий режим)
- Встановлює Gateway API CRDs, agentgateway (Helm), kagent (Helm)
- `kapply()` функція з `--validate=false` для роботи з нестабільним API-сервером
- Явно вимикає всі demo-агенти kagent (запобігає OOMKill на k3s single-node)

### `Lab1/medium/k8s/agentgateway/gateway.yaml`
- `Gateway`, `AgentgatewayBackend`, `HTTPRoute` ресурси
- Gateway API v1 (`gateway.networking.k8s.io/v1`)

### `Lab1/medium/k8s/kagent/`
- `kagent-model.yaml`: `ModelConfig` (kagent.dev/v1alpha2)
- `kagent-agent.yaml`: `Agent` (kagent.dev/v1alpha2) з `type: Declarative`

## Конвенції та стандарти

### Bash скрипти
- Завжди `set -euo pipefail` або мінімум `set -e`
- Кольорові повідомлення через ANSI escape: `info()`, `warn()`, `error()`, `step()`
- Перевірка залежностей на початку скрипту
- Ніяких hardcoded секретів — тільки `${VAR:-}` з env
- Ідемпотентність: `--dry-run=client | apply` замість create

### Kubernetes маніфести
- `apiVersion` відповідно до встановлених CRDs
- Namespace явно вказано у кожному ресурсі
- Labels: `app.kubernetes.io/name`, `app.kubernetes.io/component`

### Secrets
- `.env` у `.gitignore`
- Ніяких API ключів у коді або маніфестах
- У k8s: `kubectl create secret --from-literal` з env-змінних

### Документація
- README.md у кожному lab-директорії
- Screenshots у `screenshots/` з описовими іменами

## Відомі обмеження середовища

- **k3s single-node**: SQLite backend (kine) не витримує >5 одночасних Helm інсталяцій
- **Rancher Desktop Lima VM**: обмежена пам'ять, OOMKill при запуску kagent demo-профілю
- **agentgateway k8s UI**: відсутній (тільки в standalone)
- **Traefik CRD конфлікт**: Gateway API CRDs потребують Helm ownership анотацій
