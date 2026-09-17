# План реализации Telegram Lead Radar

Текущий статус: MVP+ (итерации 1–5) реализован и проверен. Все сервисы запускаются через
Docker Compose, миграции применяются, backend-тесты и frontend production build проходят.
Для внешней приёмки остаётся указать реальные Telegram, AI и Bot credentials.

## Итерация 1 — фундамент и локально проверяемый pipeline

- Docker Compose: backend, frontend, PostgreSQL.
- FastAPI, конфигурация, SQLAlchemy и Alembic.
- Основные сущности: users, sources, messages, leads, feedback, settings.
- REST API для источников, лидов, feedback и настроек.
- Детерминированные pre-filter и Lead Score.
- Базовые страницы Dashboard, Leads, Sources и Settings.
- Unit-тесты бизнес-логики и API healthcheck.

## Итерация 2 — Telegram и полный ingestion pipeline

- MTProto через Telethon: phone/code/2FA и зашифрованная backend-only session.
- Добавление публичных username и приватных invite-ссылок.
- Join/status transitions и обработка FloodWait.
- Event-driven monitor для ACTIVE-источников.
- Нормализация, дедупликация и постановка сообщений в обработку.

Статус: реализовано.

## Итерация 3 — AI и уведомления

- Провайдер-независимый `LeadClassifier` со structured output.
- Retry 5/30/120 секунд без остановки Telegram listener.
- Сохранение результатов классификации и расчет score.
- Telegram Bot notifications, deep links и callback-feedback.
- Защита от повторных уведомлений после restart.

Статус: реализовано.

## Итерация 4 — завершение MVP

- Полный UI авторизации Telegram и управления источниками.
- Фильтры и карточка лида, ручная проверка pipeline.
- Admin-auth, безопасное удаление session, production-настройки.
- Интеграционные тесты, observability и приемочные сценарии из ТЗ.

Статус: реализовано; внешние интеграции ожидают credentials.

## Итерация 5 — MVP+

- Discovery Queries и discovery публичных чатов.
- Search Profiles, backfill и initial source analysis.
- Source Score, расширенный Dashboard и аналитика.
- Генерация черновика ответа без автоматической отправки.

Статус: реализовано; реальный discovery и backfill требуют авторизованную Telegram-сессию.
