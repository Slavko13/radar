# Telegram Lead Radar

Web-приложение для поиска запросов на IT-услуги в Telegram. MVP включает защищённую admin-панель, MTProto-контур и полный AI → Lead Score → Telegram notification pipeline с persistent retry. План дальнейшего развития находится в [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Быстрый запуск

Требуются Docker Engine и Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

После запуска:

- frontend: http://localhost:3000
- backend API: http://localhost:8000/docs
- healthcheck: http://localhost:8000/health

## Установка на Linux-сервер

После клонирования или копирования исходников выполните одну команду:

```bash
sudo bash install.sh
```

Установщик поддерживает Ubuntu/Debian, при необходимости ставит Docker, генерирует
production-секреты, хеширует пароль администратора, запускает PostgreSQL, backend,
frontend и Caddy. Для домена автоматически настраивается HTTPS; при установке по IP
используется HTTP с явным предупреждением. Подробности: [DEPLOYMENT.md](DEPLOYMENT.md).

Обновление уже установленного сервера:

```bash
sudo bash update.sh --pull
```

Пароль входа берётся из `ADMIN_PASSWORD`. В `.env.example` указано демонстрационное значение `change-me` — обязательно замените его.

Перед production-запуском обязательно замените `POSTGRES_PASSWORD` и `APP_SECRET_KEY`. Файл `.env`, Telegram session, bot token и API keys исключены из Git.

## Admin-auth и production

Весь `/api`, кроме login/status, защищён подписанной HttpOnly cookie. После пяти неверных попыток вход временно блокируется. В production обычный пароль отключается и требуется Argon2 hash.

Сгенерировать hash можно интерактивно:

```bash
docker compose run --rm backend python -c "import getpass; from argon2 import PasswordHasher; print(PasswordHasher().hash(getpass.getpass()))"
```

Укажите результат как `ADMIN_PASSWORD_HASH`. Если значение задаётся в Compose `.env`, заключите hash с символами `$` в одинарные кавычки.

```env
ENVIRONMENT=production
APP_SECRET_KEY=случайная-строка-минимум-32-символа
ADMIN_PASSWORD_HASH='$argon2id$...'
ADMIN_PASSWORD=
```

Production-конфигурация без безопасного ключа и hash не запустится. Swagger отключается автоматически. HTTPS должен завершаться на reverse proxy; backend добавляет HSTS и остальные security headers.

## Локальная backend-разработка

Проект требует Python 3.12+.

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/alembic upgrade head
.venv/Scripts/pytest
```

По умолчанию вне Docker используется SQLite. В Docker `DATABASE_URL` указывает на PostgreSQL.

## Локальная frontend-разработка

```bash
cd frontend
npm install
npm run dev
```

## Telegram API и Notification Bot

Для Telegram MTProto потребуются `api_id` и `api_hash`, полученные в разделе API Development Tools на https://my.telegram.org. Основной способ настройки — мастер в разделе Settings: инструкция → `api_id/api_hash` → телефон → код → 2FA. API credentials шифруются ключом `APP_SECRET_KEY` и сохраняются в backend volume. Переменные окружения остаются только как необязательный способ начальной конфигурации:

```env
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_SESSION_DIR=/app/data/sessions
TELEGRAM_BOT_TOKEN=
```

Содержимое пользовательской session и API credentials шифруется ключом, производным от `APP_SECRET_KEY`, не возвращается через API и не попадает в логи. Docker volume `telegram_sessions` сохраняет их после restart. Замена `APP_SECRET_KEY` делает существующую session и credentials нечитаемыми: сначала отключите аккаунт, затем смените ключ и настройте подключение заново.

Авторизация выполняется в Settings: телефон → код Telegram → при необходимости пароль 2FA. После подключения добавьте `t.me`-ссылку на странице Sources и нажмите «Вступить». Listener подписывается на updates без постоянного polling и принимает сообщения только из источников со статусом `ACTIVE`.

В разделе Sources кнопка «Показать чаты» загружает группы и каналы, в которых подключённый
аккаунт уже состоит. Личные диалоги не выводятся. Любой публичный или приватный чат из списка
можно добавить в источники без invite-ссылки; мониторинг включается сразу.

Страница «Поиск источников» хранит повторно используемые запросы и ищет публичные чаты через
Telegram MTProto. Найденные чаты получают статус `DISCOVERED`: приложение никогда не вступает
в них автоматически. После ручного вступления кнопка «Анализ 100» загружает историю, запускает
обычный pipeline с дедупликацией и рассчитывает Source Score по данным последних 30 дней.

Профили поиска задают категории, позитивные ключи, стоп-слова, обработку вакансий и собственный
порог уведомлений. Если активных профилей нет, сохраняется поведение общих настроек.

## AI provider

Классификатор настраивается через следующие переменные:

```env
AI_PROVIDER=mock
AI_API_KEY=
AI_MODEL=
AI_BASE_URL=https://api.openai.com/v1
AI_TIMEOUT_SECONDS=30
```

`AI_PROVIDER=mock` включает детерминированный локальный классификатор для проверки всего pipeline без платных запросов. Для реальной модели используйте `openai` или `openai_compatible`, укажите API key, model и совместимый `/chat/completions` base URL. Backend обращается к моделям только через абстракцию `LeadClassifier`; timeout, rate limit и некорректный JSON приводят к retry через 5, 30 и 120 секунд, не останавливая Telegram listener.

Основной способ подключения Notification Bot — мастер в разделе «Настройки»: создайте
бота через `@BotFather`, вставьте токен, отправьте боту `/start`, выберите найденный
чат и сохраните. При сохранении приложение отправит тестовое сообщение. Токен шифруется
ключом `APP_SECRET_KEY` и хранится в persistent volume, поэтому перезапуск и обновление
контейнеров не требуют повторной настройки.

Переменные окружения остаются запасным способом первоначальной конфигурации:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_NOTIFICATION_CHAT_ID=
```

Бот отправляет только лиды с оценкой не ниже пользовательского порога. `notified_at` защищает от повторной рассылки после restart. Inline-кнопки сохраняют `POSITIVE`/`NEGATIVE`; автоматическая отправка сообщений потенциальным клиентам отсутствует.
Кнопка «Подготовить ответ» в карточке лида генерирует только текстовый черновик для ручного
копирования. Backend не содержит endpoint для отправки этого текста потенциальному клиенту.

## Миграции

Backend-контейнер автоматически выполняет `alembic upgrade head` перед стартом. Вручную новую миграцию можно создать из каталога `backend`:

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Текущий API

- `GET /health`
- `POST /api/auth/login`
- `GET /api/auth/status`
- `POST /api/auth/logout`
- `GET /api/dashboard`
- `GET /api/dashboard/pipeline`
- `GET/POST /api/sources`
- `GET/PATCH/DELETE /api/sources/{id}`
- `POST /api/sources/{id}/activate`
- `POST /api/sources/{id}/pause`
- `POST /api/sources/{id}/join`
- `GET /api/sources/{id}/stats`
- `POST /api/sources/{id}/analyze`
- `GET /api/sources/telegram-dialogs`
- `POST /api/sources/import-dialog`
- `GET /api/leads`
- `GET /api/leads/{id}`
- `POST /api/leads/{id}/feedback`
- `POST /api/leads/{id}/draft-response`
- `GET/POST /api/discovery/queries`
- `PATCH/DELETE /api/discovery/queries/{id}`
- `GET /api/discovery/results`
- `POST /api/discovery/run`
- `GET/POST /api/search-profiles`
- `PATCH/DELETE /api/search-profiles/{id}`
- `GET/PATCH /api/settings`
- `GET /api/telegram/status`
- `POST /api/telegram/configure`
- `POST /api/telegram/auth/start`
- `POST /api/telegram/auth/code`
- `POST /api/telegram/auth/password`
- `POST /api/telegram/disconnect`

## Troubleshooting

- `database: unavailable`: дождитесь healthcheck PostgreSQL и проверьте `DATABASE_URL`.
- Frontend показывает ошибку backend: проверьте `VITE_API_URL` до сборки frontend.
- После копирования `.env.example` входите паролем из `ADMIN_PASSWORD`.
- `401 Authentication required`: войдите заново; срок cookie задаётся `AUTH_TOKEN_TTL_HOURS`.
- `429 Too many login attempts`: подождите пять минут перед новой попыткой.
- Изменения схемы не применились: выполните `docker compose run --rm backend alembic upgrade head`.
- Не храните реальные секреты в `.env.example`; рабочий `.env` уже находится в `.gitignore`.
