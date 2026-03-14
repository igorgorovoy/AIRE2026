# Lab1 — Beginners: agentgateway з кількома LLM провайдерами

Один скрипт встановлює agentgateway та запускає gateway з трьома backends: **Gemini**, **Anthropic**, **OpenAI**.
Провайдер обирається через заголовок `x-provider`. За замовчуванням — Gemini.

## Швидкий старт

```bash
# 1. Отримати API ключі:
#    Gemini:    https://aistudio.google.com/api-keys
#    Anthropic: https://console.anthropic.com/settings/keys
#    OpenAI:    https://platform.openai.com/api-keys

# 2. Встановити змінні (мінімум — Gemini)
export GEMINI_API_KEY=your-gemini-key
export ANTHROPIC_API_KEY=your-anthropic-key   # опціонально
export OPENAI_API_KEY=your-openai-key         # опціонально

# 3. Запустити (встановить agentgateway при першому запуску)
./run.sh
```

Після запуску:

- **UI:**  http://localhost:15000/ui/
- **API:** http://localhost:3000

---

## Що робить `run.sh`

1. **Встановлює agentgateway** — [Deploy the binary](https://agentgateway.dev/docs/standalone/latest/deployment/binary/): завантажує бінар `darwin-arm64` в `/usr/local/bin/agentgateway`.
2. **Перевіряє API ключі** — виводить статус кожного провайдера.
3. **Запускає gateway** з `config.yaml` та дає доступ через UI на http://localhost:15000/ui/.

---

## Тести

Коли gateway запущено (`./run.sh`), у **іншому терміналі** виконайте:

### Тест 1 — Gemini 2.5 Flash (за замовчуванням)

```bash
curl http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-2.5-flash",
    "messages": [{"role": "user", "content": "Привіт! Що таке agentgateway?"}]
  }'
```

Приклад успішної відповіді (скорочено):

```json
{
  "model": "gemini-2.5-flash",
  "usage": {"prompt_tokens": 9, "completion_tokens": 676, "total_tokens": 2244},
  "choices": [{
    "message": {"role": "assistant", "content": "AgentGateway — це програмний компонент..."},
    "finish_reason": "stop"
  }],
  "object": "chat.completion"
}
```

### Тест 2 — Anthropic Claude (x-provider: anthropic)

```bash
curl http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "x-provider: anthropic" \
  -d '{
    "model": "claude-3-5-haiku-20241022",
    "messages": [{"role": "user", "content": "Привіт! Що таке agentgateway?"}]
  }'
```

### Тест 3 — OpenAI GPT (x-provider: openai)

```bash
curl http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "x-provider: openai" \
  -d '{
    "model": "gpt-4.1-nano",
    "messages": [{"role": "user", "content": "Привіт! Що таке agentgateway?"}]
  }'
```

### Тест 4 — multi-turn діалог (Gemini)

```bash
curl http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-2.5-flash",
    "messages": [
      {"role": "user", "content": "Ти — DevOps-асистент. Відповідай коротко."},
      {"role": "assistant", "content": "Зрозумів! Готовий допомагати з DevOps питаннями."},
      {"role": "user", "content": "Що таке Gateway pattern в мікросервісах?"}
    ]
  }'
```

### Тест 5 — перелік доступних моделей Gemini

```bash
curl "https://generativelanguage.googleapis.com/v1/models?key=$GEMINI_API_KEY" \
  | python3 -m json.tool | grep '"name"'
```

Доступні моделі (підтверджено):

```
"name": "models/gemini-2.5-flash"
"name": "models/gemini-2.5-pro"
"name": "models/gemini-2.0-flash"
"name": "models/gemini-2.0-flash-001"
"name": "models/gemini-2.0-flash-lite-001"
"name": "models/gemini-2.0-flash-lite"
"name": "models/gemini-2.5-flash-lite"
```

---

## UI — agentgateway

### Overview (Home)

![UI Overview](screenshots/ui-overview.png)

Головна сторінка показує загальний стан gateway: 1 Port Bind, 1 Listener (`AIRE2026`), 3 Routes, 3 Backends. Статус `Configuration looks good!` — всі listeners мають routes, всі routes мають backends.

### Backends

![UI Backends](screenshots/ui-backends.png)

Три AI backends, прив'язані до listener `AIRE2026`:

| Name       | Provider  | Model                      | Route     |
|------------|-----------|----------------------------|-----------|
| anthropic  | Anthropic | `claude-3-5-haiku-20241022`| anthropic |
| openai     | OpenAI    | `gpt-4.1-nano`             | openai    |
| gemini     | Gemini    | `gemini-2.5-flash`         | gemini    |

Кожен backend має `Backend Auth` policy (ключ підставляється автоматично).

### Policies

![UI Policies](screenshots/ui-policies.png)

Три routes з policies (listener `AIRE2026`, Port 3000):

| Route     | Path | Policies                     |
|-----------|------|------------------------------|
| anthropic | `/`  | Backend Auth, CORS           |
| openai    | `/`  | Backend Auth, CORS           |
| gemini    | `/*` | Backend Auth, CORS           |

Активні policies для route `gemini`: **Backend Auth** (Active) та **CORS** (Active).

---

## Backends та Policy

У UI (http://localhost:15000/ui/) відкрийте **Routes** і **Backends**:

| Backend     | Провайдер  | Модель                   | Route (x-provider) |
|-------------|------------|--------------------------|--------------------|
| `gemini`    | Gemini     | `gemini-2.5-flash`       | *(за замовчуванням)* |
| `anthropic` | Anthropic  | `claude-3-5-haiku-20241022` | `anthropic`    |
| `openai`    | OpenAI     | `gpt-4.1-nano`           | `openai`           |

### Policy (політики) у `config.yaml`

- **cors** — дозволяє запити з будь-якого origin/header (для тестування).
- **backendAuth** — підставляє відповідний API ключ (`$GEMINI_API_KEY`, `$ANTHROPIC_API_KEY`, `$OPENAI_API_KEY`) в запити до провайдера. Клієнт ключ не бачить.

Детальніше:

- [Providers](https://agentgateway.dev/docs/standalone/latest/llm/providers/)
- [Backends](https://agentgateway.dev/docs/standalone/latest/configuration/backends)
- [Security (auth, CORS)](https://agentgateway.dev/docs/standalone/latest/configuration/security)
- [Multiple LLM providers](https://agentgateway.dev/docs/standalone/latest/llm/providers/multiple-llms)

---

## Файли

| Файл          | Опис |
|---------------|------|
| `run.sh`      | Встановлення agentgateway, перевірка ключів, запуск gateway. |
| `config.yaml` | Три routes/backends (Gemini, Anthropic, OpenAI) з routing за `x-provider`. |
| `README.md`   | Інструкції, тести, опис Backends і Policy. |
