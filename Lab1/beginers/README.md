# Lab1 — Beginners: agentgateway з Google Gemini

Один скрипт виконує встановлення, налаштування та запуск gateway. Далі — перевірка доступу до LLM та основи Backends і Policy.

## Швидкий старт

```bash
# 1. Отримати API ключ Gemini
#    https://aistudio.google.com/api-keys

# 2. Встановити змінну середовища
export GEMINI_API_KEY=your-api-key

# 3. Запустити (встановить agentgateway при першому запуску)
./run.sh
```

Після запуску:

- **UI:** http://localhost:15000/ui/
- **API:** http://localhost:3000

---

## Що робить `run.sh`

1. **Встановлює agentgateway** — [Deploy the binary](https://agentgateway.dev/docs/standalone/latest/deployment/binary/): завантажує бінар для вашої ОС/архітектури в `/usr/local/bin/agentgateway`.
2. **Обирає LLM провайдера** — [Providers](https://agentgateway.dev/docs/standalone/latest/llm/providers/): у цьому лабі використовується **Google Gemini** (AI Studio).
3. **Налаштовує config.yaml** — [LLM Gateway tutorial](https://agentgateway.dev/docs/standalone/latest/tutorials/llm-gateway/): один route на порту 3000 з backend `gemini` та політиками CORS і backendAuth.
4. **Запускає gateway** і дає доступ через UI по http://localhost:15000/ui/.

---

## Перевірка доступу до LLM

Коли gateway запущено (`./run.sh`), у **іншому терміналі** виконайте:

```bash
curl http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-2.5-flash",
    "messages": [{"role": "user", "content": "Привіт! Скажи одним реченням, що таке agentgateway."}]
  }'
```

Успішна відповідь містить `"choices"` з полем `message.content`. Якщо є помилка авторизації — перевірте `GEMINI_API_KEY` та ключ на https://aistudio.google.com/api-keys.

### Перевірка доступних моделей

```bash
curl "https://generativelanguage.googleapis.com/v1/models?key=$GEMINI_API_KEY" \
  | python3 -m json.tool | grep '"name"'
```

---

## Backends та Policy (коротко)

У UI (http://localhost:15000/ui/) перегляньте:

### Backends

- **Backends** — це цільові сервіси, до яких gateway проксує запити.
- У цьому лабі є один backend типу **AI**: **gemini** (провайдер Gemini, модель `gemini-2.0-flash`).
- Кожен backend має ім’я, провайдера, модель і набір політик.

### Policy (політики)

- **policies** визначають, як обробляти трафік для маршруту/backend.
- У `config.yaml` для маршруту задано:
  - **cors** — дозволені origins/headers для браузера.
  - **backendAuth** — ключ `$GEMINI_API_KEY` підставляється в запити до Gemini.

Детальніше:

- [Configuration overview](https://agentgateway.dev/docs/standalone/latest/configuration/)
- [Backends](https://agentgateway.dev/docs/standalone/latest/configuration/backends)
- [Security (auth, CORS)](https://agentgateway.dev/docs/standalone/latest/configuration/security)

---

## Файли

| Файл         | Опис |
|--------------|------|
| `run.sh`     | Встановлення agentgateway, перевірка ключа, запуск gateway з `config.yaml`. |
| `config.yaml`| Конфіг для одного route (port 3000) з backend Gemini та політиками. |
| `README.md`  | Інструкції та пояснення Backends/Policy. |

## Інші провайдери

Приклад конфігу для одного провайдера є в [LLM Gateway tutorial](https://agentgateway.dev/docs/standalone/latest/tutorials/llm-gateway/) (OpenAI, Anthropic, Gemini, Bedrock, Azure, Ollama). Щоб використати інший провайдер, змініть `config.yaml` за цим туторіалом і при потребі додайте відповідні змінні середовища (наприклад, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`).
