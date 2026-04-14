# ИИ-ассистент: сбор лидов для отдела продаж (Telegram)

[![CI](https://github.com/Edwards359/support-intake-telegram-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/Edwards359/support-intake-telegram-bot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Telegram-бот для квалификации входящих лидов: диалог с клиентом, извлечение полей через LLM (Chat Completions + JSON Schema), структурированное сообщение в чат менеджеров по продажам.

## Возможности

- пошаговый сбор обязательных полей лида в чате;
- вызов OpenAI-совместимого API с fallback при сбоях;
- отправка готового лида в указанный Telegram-чат;
- запуск локально, в Docker или через Docker Compose.

## Что собирает ассистент

- имя;
- контакт (телефон, email или Telegram);
- компания или тип клиента (в т.ч. «частное лицо»);
- суть интереса / задачи;
- сроки принятия решения (фиксированные варианты);
- температура лида: горячий / тёплый / холодный.

## Структура репозитория

```text
.
├── bot/                    # aiogram: роутеры, хендлеры
├── core/                   # настройки, логирование, схемы (SalesLead, LeadSession)
├── services/               # ассистент, хранилище сессий, уведомления
├── scripts/                # генерация DOCX/PDF ответа на задание (не в Docker-образе)
├── assignment/             # сюда пишется готовый DOCX/PDF (локально)
├── .env.example
├── .github/workflows/ci.yml
├── docker-compose.yml
├── Dockerfile
├── main.py
├── requirements.txt
└── requirements-docs.txt   # зависимости только для сборки отчёта
```

## Переменные окружения

Скопируйте `.env.example` в `.env` и задайте значения (см. комментарии в шаблоне).

| Переменная | Описание |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | токен бота от [@BotFather](https://t.me/BotFather) |
| `OPERATOR_CHAT_ID` | ID чата/супергруппы для лидов (часто отрицательный) |
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

```bash
docker build -t sales-lead-bot .
docker run --rm --env-file .env sales-lead-bot
```

Или Compose (сервис `sales-lead-bot`, подхватывает `.env` в корне проекта):

```bash
docker compose up --build -d
```

## Как это устроено

1. Клиент пишет боту (или жмёт `/start`).
2. Сессия хранится в памяти процесса (`LeadSession` + история).
3. `OpenAILeadAssistant` передаёт в модель `current_lead`, историю и новое сообщение.
4. Модель возвращает JSON: `reply`, `extracted_lead`, `ready_to_submit`.
5. Когда все обязательные поля заполнены и `ready_to_submit=true`, лид уходит в чат менеджеров.
6. Клиент получает финальное подтверждение.

## Ответ на задание (DOCX → PDF)

```powershell
pip install -r requirements-docs.txt
python scripts/build_assignment_doc.py
```

Файлы появятся в каталоге `assignment/`: `Ответ_на_задание.docx` и при успешной конвертации `Ответ_на_задание.pdf` (для `docx2pdf` на Windows обычно нужен установленный Microsoft Word).

## CI

В GitHub Actions выполняется установка зависимостей и проверка синтаксиса (`python -m compileall`).

## Важно

- Сессии в памяти: после перезапуска бота контекст диалогов теряется.
- Если у пользователя есть `@username`, бот может подставить его как контакт по умолчанию.
- Не коммитьте `.env` и секреты.

## Репозиторий на GitHub

[github.com/Edwards359/support-intake-telegram-bot](https://github.com/Edwards359/support-intake-telegram-bot)

```bash
git clone https://github.com/Edwards359/support-intake-telegram-bot.git
cd support-intake-telegram-bot
```

Перед коммитом проверяйте `git status`: в индексе не должно быть `.env`. Если Git сообщает о **dubious ownership** для каталога на диске `D:`, добавьте путь в исключения:  
`git config --global --add safe.directory "D:/полный/путь/к/клону"`
