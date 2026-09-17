# Техническое задание
## Telegram Lead Radar — система поиска потенциальных клиентов в Telegram

## 1. Цель проекта

Необходимо разработать web-приложение, которое автоматически:

- ищет потенциально полезные Telegram-чаты;
- позволяет подключать найденные чаты к мониторингу;
- получает новые сообщения из подключенных чатов через Telegram-аккаунт пользователя;
- определяет сообщения, в которых люди ищут исполнителей или подрядчиков;
- классифицирует такие сообщения;
- присваивает им оценку качества — Lead Score;
- отправляет лучшие лиды пользователю в Telegram;
- сохраняет историю лидов;
- собирает статистику по эффективности источников.

Основная задача:

> как можно быстрее находить сообщения людей, которым нужны IT-услуги, и давать пользователю возможность сразу связаться с потенциальным клиентом.

---

# 2. Пример целевого сообщения

Например, в одном из Telegram-чатов появляется сообщение:

> Коллеги, посоветуйте разработчика. Нужно сделать сайт для компании, желательно запустить в течение месяца.

Система должна:

1. получить сообщение;
2. определить, что оно похоже на запрос услуги;
3. передать его AI-классификатору;
4. определить, что автор действительно ищет исполнителя;
5. определить категорию — Web Development;
6. определить запрос — разработка сайта;
7. рассчитать Lead Score;
8. отправить пользователю уведомление;
9. дать кнопку перехода к оригинальному сообщению.

Пример уведомления:

```text
🔥 Новый лид — 94/100

Нужна разработка сайта для компании.

Категория:
Web Development

Срочность:
Средняя

Бюджет:
Не указан

Чат:
Предприниматели Москвы

Автор:
@username

[Открыть сообщение]

[✅ Хороший лид]
[❌ Не лид]
```

---

# 3. Общая архитектура

Система является полноценным клиент-серверным web-приложением.

```text
                    ┌────────────────────┐
                    │     Пользователь   │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │      Frontend      │
                    │ React / TypeScript │
                    └─────────┬──────────┘
                              │
                           REST API
                              │
                              ▼
                    ┌────────────────────┐
                    │      Backend       │
                    │      FastAPI       │
                    └─────────┬──────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
 ┌────────────────┐   ┌───────────────┐   ┌──────────────┐
 │ Telegram Client│   │ PostgreSQL    │   │ AI / LLM API │
 │ MTProto        │   │               │   │              │
 └───────┬────────┘   └───────────────┘   └──────────────┘
         │
         ▼
 ┌────────────────┐
 │ Telegram User  │
 │ Session        │
 └────────────────┘

          Backend
             │
             ▼
    ┌──────────────────┐
    │ Telegram Bot API │
    │ Уведомления      │
    └──────────────────┘
```

---

# 4. Основные компоненты

Система должна состоять из следующих модулей:

1. Frontend.
2. Backend API.
3. Telegram Account Manager.
4. Telegram Monitor.
5. Chat Discovery.
6. Source Manager.
7. Message Pre-filter.
8. AI Lead Detector.
9. Lead Scoring.
10. Lead Storage.
11. Notification Service.
12. Feedback.
13. Analytics.
14. PostgreSQL.
15. Background Workers.

---

# 5. Telegram-интеграция

Для чтения чатов использовать не обычного Telegram-бота, а пользовательский Telegram-аккаунт через MTProto API.

После авторизации Telegram API выполняет последующие запросы от имени авторизованного пользователя. Авторизация сохраняется через клиентскую Telegram-сессию.

Telegram официально поддерживает пользовательскую авторизацию через номер телефона, код, 2FA, QR и другие механизмы.

Telegram Bot используется отдельно — только для отправки уведомлений пользователю.

Таким образом:

```text
Telegram User Session
→ чтение доступных пользователю чатов

Telegram Bot
→ отправка лидов и уведомлений
```

---

# 6. Авторизация Telegram-аккаунта

На странице настроек пользователь должен иметь возможность подключить Telegram.

Процесс:

```text
Ввести номер телефона
        ↓
Получить код Telegram
        ↓
Ввести код
        ↓
При необходимости ввести пароль 2FA
        ↓
Создается Telegram session
        ↓
Аккаунт подключен
```

После успешной авторизации повторный ввод кода при каждом запуске системы не требуется, пока Telegram-сессия остается действительной.

---

# 7. Telegram session

Telegram-session является критическим секретом.

Требования:

- не хранить в Git;
- не передавать на frontend;
- не выводить содержимое session в логи;
- хранить только на backend;
- ограничить доступ к session;
- хранить секреты через environment variables / secret storage;
- предусмотреть возможность отключить Telegram-аккаунт и удалить session.

---

# 8. Главный пользовательский процесс

Общий процесс работы системы:

```text
ПОИСК ЧАТОВ
      ↓
ОЦЕНКА ЧАТОВ
      ↓
ДОБАВЛЕНИЕ В МОНИТОРИНГ
      ↓
ПОЛУЧЕНИЕ НОВЫХ СООБЩЕНИЙ
      ↓
PRE-FILTER
      ↓
AI-АНАЛИЗ
      ↓
LEAD SCORE
      ↓
СОХРАНЕНИЕ ЛИДА
      ↓
УВЕДОМЛЕНИЕ
      ↓
ПОЛЬЗОВАТЕЛЬ ОТКРЫВАЕТ TELEGRAM
      ↓
СВЯЗЫВАЕТСЯ С КЛИЕНТОМ
```

---

# 9. Поиск Telegram-чатов — Chat Discovery

Необходимо реализовать модуль поиска потенциальных источников лидов.

Система должна работать с:

- публичными Telegram-группами;
- супергруппами;
- каналами;
- приватными группами, если найдена доступная invite-ссылка.

Приватные Telegram-сообщества могут использовать ссылки формата:

```text
t.me/+...
```

Telegram поддерживает проверку invite-ссылок и сценарии, когда вступление требует подтверждения администратора.

---

# 10. Discovery Queries

Пользователь должен иметь возможность задавать поисковые запросы.

Например:

```text
бизнес
предприниматели
стартапы
фриланс
маркетинг
подрядчики
тендеры
разработка
digital
бизнес Москва
предприниматели Москва
малый бизнес
стартап Москва
IT бизнес
```

Запросы должны:

- добавляться;
- редактироваться;
- включаться;
- выключаться;
- удаляться.

---

# 11. Внешний Discovery

Архитектурно предусмотреть возможность искать Telegram-ссылки во внешних публичных источниках.

Например:

```text
поисковые системы
каталоги Telegram
публичные сайты
статьи
бизнес-сообщества
публичные Telegram-каналы
```

Искомые ссылки:

```text
t.me/name
t.me/+HASH
t.me/joinchat/HASH
```

На MVP полноценный внешний web-discovery может не входить.

---

# 12. Приватные чаты

Система не должна обещать поиск всех закрытых Telegram-групп.

Приватный чат можно обнаружить, если:

- пользователь добавил invite-ссылку вручную;
- invite-ссылка была опубликована в доступном источнике;
- ссылка была обнаружена Discovery-модулем.

Статусы invite:

```text
AVAILABLE
JOIN_REQUEST_REQUIRED
ALREADY_MEMBER
EXPIRED
INVALID
JOINED
REJECTED
```

---

# 13. Вступление в чат

Массовое автоматическое вступление в группы на первом этапе не использовать.

Рекомендуемый процесс:

```text
Система нашла чат
        ↓
Показала пользователю
        ↓
Пользователь нажал "Вступить"
        ↓
Backend выполняет Telegram API action
        ↓
Чат подключается
```

Если требуется approval администратора:

```text
JOIN_REQUEST_REQUIRED
```

---

# 14. Sources — список источников

В web-интерфейсе должна быть страница:

## Источники

Таблица:

```text
Название
Тип
Username
Public / Private
Участники
Статус
Активность
Leads 30d
Source Score
```

---

# 15. Статусы источников

```text
DISCOVERED
REVIEW
APPROVED
JOIN_PENDING
ACTIVE
PAUSED
REJECTED
LEFT
UNAVAILABLE
```

---

# 16. Действия с источниками

Пользователь может:

- добавить ссылку вручную;
- добавить username;
- одобрить найденный чат;
- вступить;
- включить мониторинг;
- выключить мониторинг;
- удалить источник;
- посмотреть сообщения;
- посмотреть найденные лиды;
- посмотреть статистику.

---

# 17. Telegram Monitor

Для всех источников:

```text
status = ACTIVE
```

backend должен получать новые сообщения максимально близко к real-time.

Не использовать постоянный polling там, где библиотека позволяет подписываться на Telegram updates.

---

# 18. Типы сообщений

На MVP анализировать:

- обычные текстовые сообщения;
- caption к изображениям;
- caption к видео;
- ответы на сообщения.

Позже:

- voice;
- OCR;
- документы;
- изображения;
- видео.

---

# 19. Хранение сообщения

Минимальные данные:

```text
telegram_message_id
telegram_chat_id
thread_id
sender_id
sender_username
sender_name
text
date
edit_date
reply_to_message_id
message_url
created_at
```

---

# 20. Ссылка на оригинальное сообщение

Для каждого лида должна быть возможность открыть оригинальное сообщение.

Telegram поддерживает ссылки как на публичные, так и на доступные пользователю приватные сообщения.

Кнопка:

```text
Открыть сообщение
```

должна вести непосредственно в Telegram.

---

# 21. Pipeline обработки сообщения

Каждое новое сообщение проходит:

```text
Telegram Message
       ↓
Normalization
       ↓
Duplicate Check
       ↓
Pre-filter
       ↓
AI classification
       ↓
Lead Score
       ↓
Save Lead
       ↓
Notify User
```

---

# 22. Pre-filter

Нельзя отправлять каждое сообщение из чатов в LLM.

До AI необходимо использовать быстрый фильтр.

Положительные признаки:

```text
нужен
нужна
нужно
ищу
ищем
требуется
посоветуйте
порекомендуйте
кто может
кто сделает
кто занимается
нужен подрядчик
ищем подрядчика
ищем специалиста
нужна команда
заказать
разработать
сделать
доработать
автоматизировать
интегрировать
```

---

# 23. Предметные признаки

```text
сайт
лендинг
интернет-магазин
web
приложение
мобильное приложение
telegram bot
бот
CRM
1С
API
интеграция
автоматизация
AI
LLM
нейросеть
QA
тестирование
дизайн
frontend
backend
разработка
```

Списки должны быть настраиваемыми.

---

# 24. AI Lead Detector

После pre-filter сообщение отправляется в AI.

AI должен ответить:

1. является ли сообщение потенциальным лидом;
2. что необходимо клиенту;
3. какую категорию услуги выбрать;
4. ищет ли человек исполнителя;
5. насколько система уверена;
6. есть ли бюджет;
7. есть ли срок;
8. есть ли срочность;
9. кратко сформулировать суть запроса.

---

# 25. Structured Output

AI должен возвращать строго структурированный объект.

Пример:

```json
{
  "is_lead": true,
  "confidence": 0.96,
  "category": "WEB_DEVELOPMENT",
  "service": "CORPORATE_WEBSITE",
  "intent": "LOOKING_FOR_CONTRACTOR",
  "urgency": "MEDIUM",
  "budget": null,
  "budget_currency": null,
  "deadline": null,
  "summary": "Ищет разработчика корпоративного сайта",
  "reason": "Автор напрямую просит порекомендовать исполнителя"
}
```

---

# 26. Категории

Начальный набор:

```text
WEB_DEVELOPMENT
ECOMMERCE
MOBILE_DEVELOPMENT
TELEGRAM_BOTS
CRM
ERP_1C
INTEGRATIONS
AUTOMATION
AI_LLM
QA
DESIGN
DEVOPS
DATA
CONSULTING
OTHER
```

Категории должны быть расширяемыми.

---

# 27. Intent

```text
LOOKING_FOR_CONTRACTOR
LOOKING_FOR_SPECIALIST
REQUEST_FOR_RECOMMENDATION
REQUEST_FOR_ESTIMATE
REQUEST_FOR_CONSULTATION
OUTSOURCING
TENDER
OTHER
NOT_A_LEAD
```

---

# 28. Что считать лидом

Лид:

> Посоветуйте разработчика, который сможет сделать интернет-магазин.

Лид:

> Нужна команда для разработки приложения.

Лид:

> Кто может интегрировать сайт с 1С?

Лид:

> Есть кто занимается автоматизацией отдела продаж?

---

# 29. Что не считать лидом

Не лид:

> Я разработчик сайтов, беру новые проекты.

Не лид:

> Есть вакансия frontend-разработчика в штат.

Не лид:

> Кто сейчас учится frontend?

Не лид:

> Вышла новая версия React.

Не лид:

> Продам курс по разработке сайтов.

---

# 30. Фильтрация вакансий

На MVP вакансии штатных сотрудников по умолчанию считать:

```text
NOT_A_LEAD
```

Но предусмотреть настройку:

```text
Include vacancies = true/false
```

---

# 31. Lead Score

Каждый лид получает оценку:

```text
0–100
```

Пример шкалы:

```text
90–100 HOT
75–89 GOOD
60–74 POSSIBLE
0–59 IGNORE
```

---

# 32. Факторы Lead Score

Учитывать:

- ищет ли человек конкретного исполнителя;
- соответствует ли запрос нашим услугам;
- насколько конкретно сформулирована задача;
- указан ли бюджет;
- указан ли срок;
- срочность;
- AI confidence;
- качество источника;
- отрицательные признаки.

Точную формулу можно вынести в конфигурацию.

---

# 33. Порог уведомлений

В настройках:

```text
Minimum notification score
```

По умолчанию:

```text
70
```

Пользователь может изменить.

---

# 34. Уведомления

Отдельный Telegram Bot должен присылать лид пользователю.

Пример:

```text
🔥 НОВЫЙ ЛИД

Score: 94/100

Нужен разработчик сайта для компании.

Категория:
Web Development

Бюджет:
Не указан

Срок:
В течение месяца

Чат:
Предприниматели Москвы

Автор:
@username

[🚀 Открыть сообщение]

[✅ Хороший лид]
[❌ Не лид]
```

---

# 35. Автоматическая отправка сообщений клиентам

На MVP:

**запрещена.**

Система:

```text
ищет → анализирует → уведомляет
```

но не пишет людям автоматически.

Пользователь самостоятельно принимает решение о контакте.

---

# 36. Генерация ответа

Как дополнительная функция:

```text
[✨ Подготовить ответ]
```

AI формирует черновик:

> Здравствуйте! Увидел ваш запрос по поводу разработки сайта. Мы занимаемся подобными проектами. Могу уточнить несколько моментов и предварительно сориентировать вас по срокам и стоимости.

Система только генерирует текст.

Автоматически не отправляет.

---

# 37. Feedback

Для каждого лида:

```text
✅ Хороший лид
❌ Не лид
```

Сохранять:

```text
POSITIVE
NEGATIVE
```

---

# 38. Использование Feedback

Feedback используется для:

- оценки качества AI;
- настройки prompts;
- настройки Lead Score;
- анализа false positive;
- анализа эффективности источников;
- потенциального обучения классификатора в будущем.

---

# 39. Дедупликация

Одно Telegram-сообщение не должно отправляться несколько раз.

Unique:

```text
telegram_chat_id
+
telegram_message_id
```

Дополнительно желательно обнаруживать одинаковый текст, опубликованный в нескольких сообществах.

---

# 40. История лидов

Страница:

## Leads

Таблица:

```text
Дата
Score
Категория
Источник
Автор
Summary
Feedback
Status
```

---

# 41. Фильтры лидов

Фильтрация:

- по дате;
- по категории;
- по Score;
- по источнику;
- HOT / GOOD / POSSIBLE;
- подтвержденные;
- отклоненные;
- без feedback.

---

# 42. Карточка лида

Показывать:

- оригинальный текст;
- автора;
- источник;
- время;
- категорию;
- service;
- intent;
- AI confidence;
- Lead Score;
- бюджет;
- срок;
- AI summary;
- explanation;
- feedback;
- кнопку Telegram.

---

# 43. Dashboard

Главный экран.

Пример:

```text
Сегодня

Получено сообщений: 8 240

Прошли pre-filter: 241

Проверено AI: 241

Лидов: 22

HOT: 4
GOOD: 9
POSSIBLE: 9

Подтверждено пользователем: 11
```

---

# 44. Source Score

Для каждого Telegram-источника рассчитывать полезность.

Например:

```text
Предприниматели Москвы

Сообщений за 30 дней:
18 200

Найдено лидов:
48

Подтверждено:
36

False Positive:
5

Source Score:
9.1 / 10
```

---

# 45. Назначение Source Score

Пользователь должен быстро понимать:

```text
какие чаты дают лиды
```

и

```text
какие чаты создают только нагрузку
```

---

# 46. Search Profiles

Предусмотреть сущность Search Profile.

Например:

```text
Разработка
```

Внутри:

```text
Сайты
Приложения
Боты
CRM
AI
Интеграции
Автоматизация
```

---

# 47. Настройки Search Profile

```text
name
description
enabled
categories
positive_keywords
negative_keywords
min_score
include_vacancies
notification_enabled
```

---

# 48. Frontend

Рекомендуемый стек:

```text
React
TypeScript
```

Допустим Next.js.

---

# 49. Основные страницы Frontend

```text
Dashboard
Leads
Sources
Discovery
Search Profiles
Settings
Telegram Account
```

---

# 50. Settings

Пользователь должен видеть:

## Telegram Account

```text
Connected / Disconnected
Phone
Account Name
Session status
Disconnect
```

## Notification Bot

```text
Connected / Disconnected
```

## AI

```text
Provider
Model
Status
```

## Lead Settings

```text
Minimum Score
Categories
Vacancies
```

---

# 51. Backend

Рекомендуемый стек:

```text
Python 3.12+
FastAPI
```

Причина выбора Python:

- хорошие библиотеки Telegram;
- удобная работа с AI;
- async;
- быстрый MVP.

---

# 52. Telegram Library

Рекомендуется:

```text
Telethon
```

Допускается:

```text
Pyrogram
TDLib
```

если разработчик аргументированно предпочитает другой вариант.

---

# 53. Database

Использовать:

```text
PostgreSQL
```

---

# 54. ORM

Рекомендуется:

```text
SQLAlchemy
```

---

# 55. Миграции

```text
Alembic
```

---

# 56. Background Processing

На небольшом MVP допустимо:

```text
asyncio workers
```

При дальнейшем масштабировании:

```text
Redis
Celery / RQ / другой queue worker
```

---

# 57. Основные таблицы БД

## users

```text
id
name
created_at
```

Даже если MVP однопользовательский, желательно заложить user_id.

---

## telegram_accounts

```text
id
user_id
telegram_user_id
phone
username
status
session_reference
created_at
updated_at
```

---

## sources

```text
id
user_id
telegram_chat_id
type
title
username
description
url
invite_url
is_public
participants_count
status
source_score
discovery_source
discovery_query
joined_at
last_message_at
created_at
updated_at
```

---

## messages

```text
id
source_id
telegram_message_id
sender_id
sender_username
sender_name
text
message_date
edit_date
thread_id
reply_to_message_id
message_url
prefilter_result
created_at
```

---

## leads

```text
id
message_id
search_profile_id
is_lead
confidence
lead_score
category
service
intent
urgency
budget
budget_currency
deadline
summary
reason
status
notified_at
created_at
updated_at
```

---

## lead_feedback

```text
id
lead_id
user_id
feedback
created_at
```

---

## search_profiles

```text
id
user_id
name
description
enabled
min_score
include_vacancies
created_at
updated_at
```

---

## discovery_queries

```text
id
user_id
query
enabled
last_run_at
created_at
updated_at
```

---

# 58. Backend API

Пример.

## Sources

```text
GET    /api/sources
POST   /api/sources
GET    /api/sources/{id}
PATCH  /api/sources/{id}
DELETE /api/sources/{id}

POST /api/sources/{id}/join
POST /api/sources/{id}/activate
POST /api/sources/{id}/pause
POST /api/sources/{id}/analyze
```

---

## Leads

```text
GET  /api/leads
GET  /api/leads/{id}
POST /api/leads/{id}/feedback
```

---

## Discovery

```text
GET  /api/discovery/results
POST /api/discovery/run
```

---

## Search Queries

```text
GET    /api/discovery/queries
POST   /api/discovery/queries
PATCH  /api/discovery/queries/{id}
DELETE /api/discovery/queries/{id}
```

---

## Telegram

```text
GET  /api/telegram/status

POST /api/telegram/auth/start
POST /api/telegram/auth/code
POST /api/telegram/auth/password
POST /api/telegram/disconnect
```

---

## Settings

```text
GET   /api/settings
PATCH /api/settings
```

---

# 59. AI Provider

AI должен быть абстрагирован от конкретного поставщика.

Интерфейс:

```text
LeadClassifier
```

Метод:

```text
classify(message)
```

Backend не должен быть жестко привязан к одной модели.

---

# 60. Обработка ошибок AI

Если LLM:

- недоступен;
- вернул timeout;
- rate limit;
- неправильный JSON;

Telegram-monitoring не должен останавливаться.

Сообщение отправляется на retry.

Пример:

```text
5 секунд
30 секунд
2 минуты
```

После исчерпания:

```text
AI_PROCESSING_FAILED
```

---

# 61. Telegram FloodWait

Необходимо корректно обрабатывать Telegram API rate limits.

При FloodWait:

```text
получить время ожидания
↓
приостановить соответствующее действие
↓
продолжить после разрешенного времени
```

Не пытаться обходить ограничения Telegram.

---

# 62. Initial Source Analysis

После подключения нового чата пользователь может нажать:

```text
Проанализировать источник
```

Backend берет, например:

```text
последние 500 сообщений
```

и оценивает потенциальную эффективность.

Пример:

```text
500 сообщений

Кандидатов:
24

Лидов:
11

Сильных лидов:
7

Estimated Source Score:
8.5 / 10
```

---

# 63. Backfill

Предусмотреть возможность анализа истории:

```text
Последние 100 сообщений
Последние 500 сообщений
Последние 1000 сообщений
```

На MVP функция может быть ограничена.

---

# 64. Логи

Логировать:

- старт приложения;
- Telegram connection;
- reconnect;
- authorization;
- source added;
- source status changed;
- processing errors;
- AI errors;
- Telegram errors;
- FloodWait;
- notifications;
- Discovery execution.

---

# 65. Что нельзя логировать

```text
Telegram session
Telegram auth keys
2FA password
Bot token
API keys
```

---

# 66. Healthcheck

```text
GET /health
```

Ответ:

```json
{
  "status": "ok",
  "database": "connected",
  "telegram": "connected",
  "ai": "available"
}
```

---

# 67. Deployment

Все приложение должно запускаться через Docker.

```text
docker compose up -d
```

---

# 68. Docker Compose

Минимально:

```text
backend
frontend
postgres
```

Опционально:

```text
redis
worker
```

---

# 69. Environment Variables

Пример:

```text
TELEGRAM_API_ID=
TELEGRAM_API_HASH=

TELEGRAM_BOT_TOKEN=

DATABASE_URL=

AI_PROVIDER=
AI_API_KEY=
AI_MODEL=

LEAD_SCORE_THRESHOLD=70
```

---

# 70. Repository Structure

Пример:

```text
/backend
    /api
    /telegram
    /discovery
    /lead_detection
    /notifications
    /services
    /workers
    /models

/frontend

/docker-compose.yml
/.env.example
/README.md
```

---

# 71. README

Обязательно описать:

1. требования;
2. настройку проекта;
3. получение Telegram API ID / HASH;
4. настройку Notification Bot;
5. настройку AI API;
6. запуск Docker;
7. миграции;
8. Telegram authorization;
9. troubleshooting.

---

# 72. Производительность

Цель:

```text
Telegram message
→
notification
```

при нормальной работе внешних сервисов:

```text
2–10 секунд
```

---

# 73. Масштаб MVP

Система должна быть рассчитана минимум на:

```text
100 активных Telegram-источников
```

и десятки тысяч сообщений в сутки.

---

# 74. Надежность

Перезапуск backend не должен приводить к:

- потере Telegram session;
- потере источников;
- потере лидов;
- повторной рассылке старых лидов.

---

# 75. Security

Обязательно:

- секреты только на backend;
- `.env` не коммитить;
- API keys не отдавать frontend;
- session не отдавать frontend;
- защищенная admin-auth;
- HTTPS на production;
- ограничение доступа к БД;
- возможность удалить Telegram-session.

---

# 76. Что входит в MVP

Обязательно:

1. Web frontend.
2. Backend API.
3. PostgreSQL.
4. Авторизация Telegram-пользователя.
5. Telegram session.
6. Подключение публичных Telegram-чатов.
7. Поддержка invite-ссылок.
8. Ручное добавление источника.
9. Мониторинг сообщений.
10. Pre-filter.
11. AI Lead Detector.
12. Structured Output.
13. Lead Score.
14. История лидов.
15. Страница Sources.
16. Страница Leads.
17. Telegram Bot notifications.
18. Кнопка открытия оригинального сообщения.
19. Good Lead / Not Lead.
20. Дедупликация.
21. Базовые настройки.
22. Docker Compose.
23. Logging.
24. README.

---

# 77. MVP+

Следующий этап:

1. автоматический Telegram Discovery;
2. Discovery Queries;
3. Source Score;
4. анализ истории источника;
5. Dashboard;
6. Search Profiles;
7. генерация ответа клиенту;
8. расширенная аналитика;
9. поиск публичных invite-ссылок во внешних источниках.

---

# 78. Поздние этапы

Возможные улучшения:

- OCR;
- voice-to-text;
- анализ изображений;
- собственный ML-классификатор;
- embeddings;
- CRM;
- Bitrix24;
- amoCRM;
- несколько пользователей;
- несколько Telegram-аккаунтов;
- команды продаж;
- распределение лидов;
- экспорт;
- SaaS;
- мобильное приложение.

---

# 79. Что не входит в MVP

Не требуется:

- автоматическая рассылка потенциальным клиентам;
- автодиалоги;
- массовый Telegram outreach;
- полноценная CRM;
- собственная LLM;
- OCR;
- Voice AI;
- mobile app;
- billing;
- сложный multi-tenant SaaS.

---

# 80. Критерии приемки

## Telegram Authorization

Пользователь подключает Telegram.

После restart Telegram session сохраняется.

---

## Добавление источника

Пользователь вставляет:

```text
https://t.me/example
```

Источник появляется в системе.

---

## Monitoring

После появления нового сообщения в ACTIVE-чате backend получает его.

---

## Non-lead

Сообщение:

> Всем доброе утро.

не вызывает уведомление.

---

## Lead

Сообщение:

> Посоветуйте человека, который сможет сделать сайт компании.

определяется как потенциальный лид.

---

## AI

Для лида сохраняются:

```text
category
intent
summary
confidence
lead_score
```

---

## Notification

Если Score выше установленного порога, пользователю приходит Telegram-уведомление.

---

## Original Message

Кнопка:

```text
Открыть сообщение
```

открывает исходное Telegram-сообщение.

---

## Feedback

Кнопки:

```text
Хороший лид
Не лид
```

сохраняют feedback.

---

## Duplicate

Одно сообщение не вызывает два уведомления.

---

## Restart

После:

```text
docker compose restart
```

система продолжает работу.

---

## AI Failure

Если AI временно недоступен, Telegram Listener продолжает получать сообщения.

---

## Invite Link

Валидная приватная invite-ссылка корректно определяется.

Если требуется подтверждение администратора:

```text
JOIN_REQUEST_REQUIRED
```

---

# 81. Definition of Done

MVP считается готовым, если:

1. приложение запускается через Docker Compose;
2. frontend доступен;
3. backend доступен;
4. PostgreSQL работает;
5. Telegram Account подключается;
6. Telegram session сохраняется;
7. можно добавить минимум 10 источников;
8. новые сообщения поступают в систему;
9. сообщения проходят pre-filter;
10. AI определяет лид;
11. Lead Score рассчитывается;
12. лид сохраняется;
13. уведомление приходит в Telegram;
14. оригинал открывается одной кнопкой;
15. feedback сохраняется;
16. после restart данные сохраняются;
17. дубли не рассылаются;
18. секреты отсутствуют в Git;
19. имеется README;
20. основные ошибки логируются.

---

# 82. Итоговый пользовательский процесс

```text
Пользователь подключает Telegram
             ↓
Настраивает интересующие услуги
             ↓
Система ищет Telegram-чаты
             ↓
Пользователь выбирает полезные источники
             ↓
Система мониторит сообщения
             ↓
Находит потенциальный запрос
             ↓
AI анализирует его
             ↓
Считает Lead Score
             ↓
Сохраняет лид
             ↓
Отправляет уведомление
             ↓
Пользователь открывает сообщение
             ↓
Пишет потенциальному клиенту
             ↓
Отмечает качество лида
             ↓
Система накапливает статистику
```

---

# 83. Суть продукта в одной строке

**Telegram Lead Radar автоматически находит потенциально полезные Telegram-сообщества, мониторит их, определяет с помощью AI сообщения людей, которые ищут исполнителей, и максимально быстро передает такие заявки пользователю.**