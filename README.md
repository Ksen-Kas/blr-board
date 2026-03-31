# Joe Application Assistant

Веб-сервис для автоматизации job search. Разработан для Андрея Касьянова (Senior Reservoir Engineer).

## Статус

✅ В продакшене, активная доработка

| Компонент | Где |
|-----------|-----|
| Фронтенд | Railway — `https://frontend-production-6628.up.railway.app/` |
| Бэкенд | Railway — `https://backend-production-4088.up.railway.app/` |
| Хранилище | Postgres (primary) + Google Sheets (совместимость/миграция) |
| AI | Claude API |

## Стек

- **Frontend:** React + Vite
- **Backend:** FastAPI (Python)
- **Storage:** Unified storage facade (`sheets` / `postgres` / `both`)
- **DB:** Railway Postgres
- **AI:** Anthropic Claude API
- **Deploy:** Railway (frontend + backend + postgres)

## Модель синхронизации изменений (актуально)

- В `JobCard` и `LetterScreen` изменения копятся как draft и отправляются batch-ом.
- Глобальная синхронизация доступна в Pipeline: кнопка `Sync All (N)`.
- Страховки от потери изменений:
  - autosync при выходе со страницы карточки/письма,
  - autosync на событиях `online`, `visibilitychange`, `pagehide`,
  - предупреждение `beforeunload`, если очередь не пустая.
- Очередь драфтов хранится в браузере (`localStorage`) и переживает перезагрузку страницы.
- Backend batch endpoint: `POST /api/jobs/{row_num}/batch`.

## Напоминания Telegram

- Планировщик daily reminders во web-сервисе временно отключен (runtime-off в `backend/app/services/reminder.py`).
- API `reminders/status` и `reminders/run-now` остаются в роутере, но фоновый scheduler не стартует.

## Структура проекта

```text
04_Joe-Application-Assistant/
├── CLAUDE.md              ← инструкции для агента-разработчика
├── README.md              ← этот файл
├── frontend/              ← React приложение
├── backend/               ← FastAPI сервер
├── CLIENT_SPACE/          ← канонические данные клиента (CV, стратегия)
├── docs/                  ← документация
└── PROGRESS.md            ← лог изменений
```

## Где работать

- **Source repo (git):** `/Users/sizovaka/Documents/AI_LAB/Projects/04_Joe-Application-Assistant`
- **Runtime mirror (запуск):** `/Users/sizovaka/Documents/AI_LAB/RUNTIME/joe-application-assistant`

## Как продолжить работу

1. Прочитай `docs/START_HERE.md`
2. Прочитай `PROGRESS.md` и последний блок изменений
3. Проверь backend env (`DATABASE_URL`, `DATA_READ_SOURCE`, `DATA_WRITE_MODE`)
4. Проверь, что `CLIENT_SPACE/` содержит актуальный canonical resume

## Открытые фокусы

- Повышение стабильности/скорости pipeline и parsing
- Повышение качества извлечения JD из HH/LinkedIn
- Дальнейшая консолидация данных в Postgres с безопасной совместимостью с Google Sheets
