# ИИ-ассистент для входящих заявок в техподдержку

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

## Публикация на GitHub

1. Убедитесь, что в индексе нет секретов: `git status`, в списке не должно быть `.env`.
2. Задайте в настройках репозитория **ветку по умолчанию** `main` (или поправьте список веток в `.github/workflows/ci.yml` под вашу ветку).
3. Имя репозитория лучше выбрать коротким латиницей без пробелов — так проще клонировать и подключать CI.
4. Если Git пишет про **dubious ownership** (папка на диске принадлежит другому «владельцу» Windows), выполните:  
   `git config --global --add safe.directory "D:/полный/путь/к/этому/проекту"`

```bash
git init
git add .
git commit -m "Initial commit: Telegram support intake bot"
git branch -M main
git remote add origin https://github.com/<user>/<repo>.git
git push -u origin main
```
