# Инфраструктура

Статус: тестовый upstream-стенд закреплён и снабжён профилями OpenRouter и Ollama.

Требования к стенду:

- запуск с чистого checkout одной документированной командой;
- закреплённые версии образов и зависимостей;
- `.env.example` без секретов;
- health/readiness check и короткий smoke test;
- отдельные профили или конфигурации для разработки и демонстрации;
- журналирование версии модели, конфигурации эксперимента и seed без записи секретов;
- явно зафиксированный разрешённый scope red-team тестов.

## Тестовый стенд

Используется `m-melgizin/genai-invest-agent-memory-stand` на ревизии из `stand.lock`. Код upstream клонируется в `.cache/agent-memory-stand` и не попадает в историю нашего решения.

```bash
make stand-bootstrap
make stand-up
make stand-up-openrouter
make stand-up-local
make stand-status
make stand-smoke
make stand-agent-smoke
make stand-down
```

`stand-up` автоматически выбирает OpenRouter, если в корневом `.env` задан
`OPENROUTER_API_KEY`; иначе запускает локальную Ollama с `qwen3:1.7b`. Явный
выбор доступен через `stand-up-openrouter` и `stand-up-local`. Выбранный профиль
сохраняется в игнорируемом `.cache/stand-llm-provider`, поэтому последующие
`status`, `smoke`, `logs` и `down` используют ту же Compose-конфигурацию.

OpenRouter-профиль использует `openai/gpt-5-mini` для основного ReAct-цикла и
суммаризации. Модель и лимиты можно переопределить переменными из корневого
`.env`; формат значения для upstream — `openai:<openrouter-model-slug>`.
Ключ передаётся только в окружение `agent-api`, не копируется в upstream checkout
и не выводится командами проекта.

`stand-smoke` проверяет инфраструктурные endpoints и не расходует токены
OpenRouter. `stand-agent-smoke` создаёт только локальный синтетический API-ключ
для `client1001` и делает один полный запрос через ReAct-агента; в OpenRouter-
профиле это небольшой платный запрос.

Точки входа:

- `http://localhost:3080` — LibreChat;
- `http://localhost:8501` — аккаунт и просмотр памяти;
- `http://localhost:8600/healthz` — agent API health;
- `http://localhost:8180` / `https://localhost:8443` — Keycloak;
- `http://localhost:11434/api/tags` — локальная Ollama (только local-профиль).

Тестовые пользователи upstream: `client1001` ... `client1005`, пароль совпадает с логином. Самоподписанный TLS-сертификат создаётся только в игнорируемом checkout.
