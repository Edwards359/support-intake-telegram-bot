# ИИ-ассистент для входящих заявок в техподдержку

[![CI](https://github.com/Edwards359/support-intake-telegram-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/Edwards359/support-intake-telegram-bot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Telegram-бот для первичной обработки входящих обращений: диалог с клиентом, извлечение полей через LLM (Chat Completions + JSON Schema), структурированная заявка в чат операторов.

## Возможности

- пошаговый сбор обязательных полей в чате;
- вызов OpenAI-совместимого API с fallback-логикой при сбоях;
- отправка готовой заявки в указанный Telegram-чат;
- запуск локально, в Docker или через Docker Compose.

## Что собирает ассистент

- имя клиента;
- контакт;
- описание проблемы;
- когда возникла проблема;
- где проявляется проблема;
- приоритет.

## Структура репозитория

```text
.
├── bot/                    # aiogram: роутеры, хендлеры
├── core/                   # настройки, логирование, схемы
├── services/               # ассистент, хранилище сессий, уведомления
├── .env.example            # шаблон переменных окружения
├── .github/workflows/ci.yml
├── docker-compose.yml
├── Dockerfile
├── main.py
└── requirements.txt
```

## Переменные окружения

Скопируйте `.env.example` в `.env` и задайте значения (см. комментарии в шаблоне).

| Переменная | Описание |
|------------|----------|
| `TELEGRAM_BOT_TOKEN` | токен бота от [@BotFather](https://t.me/BotFather) |
| `OPERATOR_CHAT_ID` | ID чата/супергруппы для заявок (часто отрицательный) |
| `OPENAI_API_KEY` | ключ API |
| `OPENAI_MODEL` | модель с поддержкой `response_format` типа `json_schema` |
| `OPENAI_BASE_URL` | базовый URL API (по умолчанию официальный OpenAI) |
| `LOG_LEVEL` | уровень логирования, например `INFO` |

## Локальный запуск

Требуется Python 3.12+.

**Windows (PowerShell):**

```powershell
cd <путь-к-клону-репозитория>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# отредактируйте .env
python main.py
```

**Linux / macOS:**

```bash
cd /path/to/repo
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# отредактируйте .env
python main.py
```

## Docker

Соберите образ и передайте переменные через файл `.env` или `-e`:

```bash
docker build -t support-intake-bot .
docker run --rm --env-file .env support-intake-bot
```

Или Compose (подхватывает `.env` в корне проекта):

```bash
docker compose up --build -d
```

## Как это устроено

1. Клиент пишет боту.
2. Сессия хранится в памяти процесса.
3. `OpenAISupportAssistant` передаёт в модель состояние заявки, историю и новое сообщение.
4. Модель возвращает JSON: ответ пользователю, извлечённые поля, готовность к отправке.
5. Когда все обязательные поля заполнены и модель помечает готовность, заявка уходит в чат операторов.
6. Клиент получает финальное подтверждение.

## CI

В GitHub Actions на ветках `main` и `master` выполняется установка зависимостей и проверка синтаксиса (`python -m compileall`).

## Важно

- Сессии в памяти: после перезапуска бота контекст диалогов теряется.
- Если у пользователя есть `@username`, бот может подставить его как контакт по умолчанию.
- Не коммитьте `.env` и секреты. Для продакшена имеет смысл вынести постоянное хранилище, ретраи и аудит.

## Репозиторий на GitHub

[github.com/Edwards359/support-intake-telegram-bot](https://github.com/Edwards359/support-intake-telegram-bot)

```bash
git clone https://github.com/Edwards359/support-intake-telegram-bot.git
cd support-intake-telegram-bot
```

Перед коммитом проверяйте `git status`: в индексе не должно быть `.env`. Если Git сообщает о **dubious ownership** для каталога на диске `D:`, добавьте путь в исключения:  
`git config --global --add safe.directory "D:/полный/путь/к/клону"`
