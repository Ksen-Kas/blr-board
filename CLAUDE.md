# CLAUDE.md — OPS-LAB

Таск-менеджер Ксении. Проекты: BLR, CV-LAB (позже — личные).
GitHub Pages + JSON. Автосбор из TG-чатов + автосортировка.

Полная архитектура: `ARCHITECTURE.md`

---

## Файлы

```
blr-board/
├── index.html         ← UI (НЕ ТРОГАТЬ без запроса Ксении)
├── data.json          ← данные (агент редактирует ТОЛЬКО этот файл)
├── CLAUDE.md          ← этот файл
├── ARCHITECTURE.md    ← архитектура, агенты, экономика токенов
├── agents/            ← промпты агентов (collector, sorter)
└── scripts/           ← autopush.sh (launchd)
```

**URL:** https://ksen-kas.github.io/blr-board/
**Репо:** `Ksen-Kas/blr-board` (public)
**Local:** `/Users/sizovaka/Documents/AI_LAB/GitHub/blr-board/`
**Деплой:** сохранить data.json → launchd autopush → Pages ~30 сек

---

## Как обновить (быстрый путь)

1. Edit `data.json` (точечно)
2. Обнови `updated` и `updated_at`
3. Если из Code: `git add data.json && git commit -m "update: ..." && git push`
4. Если из Cowork: просто сохрани файл — autopush сделает push

---

## Проекты в data.json

| Проект | Секции | Переключатель в UI |
|--------|--------|--------------------|
| **BLR** | inbox, fire, tasks, backlog, playbook, goals, waiting, metrics, horizons | по умолчанию |
| **CV-LAB** | cvlab | переключатель в шапке |

---

## Структура data.json

| Секция | Что | ID-префикс |
|--------|-----|------------|
| `inbox` | Входящие, не отсортированы. Вкладка "задачи" → "входящие" | `i1-i999` |
| `fire` | Горящие: сегодня/завтра, макс 7 шт | `f1-f99` |
| `tasks` | Активные задачи по категориям с приоритетами | `t1-t999` |
| `backlog` | Идеи, бэклог, долгоиграющие проекты | `b1-b999` |
| `playbook` | OPS Playbook — процессы (справочник) | `p1-p99` |
| `cvlab` | CV-LAB клиенты и идеи | `cv1-cv999` |
| `goals` | Цели Юли | — |
| `waiting` | Заблокировано | — |
| `metrics` | Метрики | — |
| `horizons` | 30/60/90 дней | — |
| `updated` | Дата (YYYY-MM-DD) | — |
| `updated_at` | ISO datetime с timezone | — |
| `last_collected_ids` | {chat_id: last_msg_id} для сборщика | — |

### Форматы

**fire / tasks:**
```json
{ "id": "t22", "title": "...", "sub": "...", "tags": [["red","горит"]], "done": false, "priority": "fire|high|mid|low" }
```

**inbox (от сборщика):**
```json
{ "id": "i1", "title": "...", "sub": "кто, откуда, когда", "urgency": "fire|week|backlog" }
```

**backlog:**
```json
{ "id": "b1", "title": "...", "sub": "источник" }
```

**Теги:** `red`, `amber`, `teal`, `purple`, `gray`

---

## Агенты

| Агент | Что делает | Расписание | Модель |
|-------|-----------|------------|--------|
| **Сборщик** | TG чаты → inbox | 4x/день (9, 13, 17, 21) | Sonnet (Cowork) |
| **Сортировщик** | inbox → fire/tasks/backlog | 2x/день (10, 18) | Sonnet (Cowork) |
| **Autopush** | data.json → git push | при изменении файла | launchd |

**Сборщик:** читает только новые сообщения (min_id), оценивает urgency из контекста.
**Сортировщик:** раскладывает по urgency от сборщика. НЕ ставит done.
**Done решает только Ксения.**

Промпты: `agents/collector-chats.md`, `agents/sorter.md`
SKILL.md для Cowork: `/Users/sizovaka/Documents/Claude/Scheduled/blr-board-*/SKILL.md`

---

## Источники задач

| Источник | Как попадает |
|----------|-------------|
| TG чаты BLR (канал, чат, Юля, публичный) | Автосбор через сборщик |
| `ksenia :: inbox` (личный TG канал) | Автосбор, каждое сообщение = задача |
| Ксения через агента | "добавь в inbox: ..." |

---

## Правила

- Редактировать ТОЛЬКО `data.json`
- НЕ трогать `index.html` без запроса Ксении
- НЕ ставить `done: true` — это решает только Ксения
- Читать `data.json` (~5KB), не index.html — экономия токенов
- Push только в main
- Всегда обновлять `updated` и `updated_at`

---

## Доступ

| Агент | Как работает |
|-------|-------------|
| **Claude Code** | Edit → git commit → git push |
| **Cowork (Desktop)** | Edit → сохранить → autopush |
| **Codex** | Напрямую через git |
| **Ксения с телефона** | TG → ksenia :: inbox → сборщик подхватит |

---

## Контекст

**Ксения Сизова** — Community Ops Manager (BLR), карьерный консультант (CV-LAB).
**BLR:** подписочное AI-комьюнити. Цель: churn 45% → 20% за 90 дней.
**CV-LAB:** работа с клиентами по карьерному консалтингу.
Подробнее: `/Users/sizovaka/Documents/AI_LAB/Projects/06_BLR/CLAUDE.md`
