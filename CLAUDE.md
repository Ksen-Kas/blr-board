# CLAUDE.md — BLR Board

Интерактивная доска задач BLR-комьюнити. GitHub Pages + JSON.
Полная архитектура системы агентов: `ARCHITECTURE.md`.

---

## Файлы

```
blr-board/
├── index.html        ← UI (НЕ ТРОГАТЬ без запроса Ксении)
├── data.json         ← данные доски (агент редактирует ТОЛЬКО этот файл)
├── CLAUDE.md         ← этот файл (быстрый старт для агента)
└── ARCHITECTURE.md   ← полная архитектура, план развития, экономика токенов
```

**URL:** `https://ksen-kas.github.io/blr-board/`
**Репо:** `Ksen-Kas/blr-board` (public)
**Local:** `/Users/sizovaka/Documents/AI_LAB/GitHub/blr-board/`
**Деплой:** push в main → Pages обновляется ~30 сек

---

## Как обновить доску (быстрый путь)

```bash
cd /Users/sizovaka/Documents/AI_LAB/GitHub/blr-board
# 1. Edit data.json (точечно, через Edit tool)
# 2. Обнови "updated" на текущую дату
git add data.json && git commit -m "update: описание" && git push
```

---

## Структура data.json

| Секция | Что | ID-префикс |
|--------|-----|------------|
| `inbox` | Входящие, не отсортированы (показываются в табе "горит" оранжевым) | `i1-i999` |
| `fire` | Горящие: сегодня/завтра, макс 5-7 шт | `f1-f99` |
| `tasks` | Активные задачи по категориям с приоритетами | `t1-t999` |
| `backlog` | Идеи, бэклог, долгоиграющие проекты по категориям | `b1-b999` |
| `playbook` | OPS Playbook — 16 процессов (справочник, не задачи) | `p1-p99` |
| `goals` | Цели Юли | — |
| `waiting` | Заблокировано, ждём от кого-то | — |
| `metrics` | Ключевые метрики | — |
| `horizons` | 30/60/90 дней | — |
| `updated` | Дата обновления (YYYY-MM-DD) | — |

### Формат задачи (fire / tasks)

```json
{
  "id": "t22",
  "title": "название",
  "sub": "описание",
  "tags": [["red","горит"], ["amber","эта неделя"]],
  "done": false,
  "priority": "fire|high|mid|low"
}
```

### Формат inbox

```json
{ "id": "i1", "title": "что прилетело", "sub": "откуда / контекст" }
```

### Формат backlog

```json
{ "id": "b1", "title": "идея", "sub": "источник или контекст" }
```

**Цвета тегов:** `red`, `amber`, `teal`, `purple`, `gray`.

### Поток карточек

```
inbox → сортировка → fire | tasks | backlog | удалить (шум)
fire/tasks → done: true → через время удалить из JSON
```

---

## Правила

- Редактировать ТОЛЬКО `data.json`
- Не трогать `index.html` без явного запроса Ксении
- Не менять структуру JSON
- Пушить только в main
- Всегда обновлять поле `"updated"`
- Читать только `data.json` (~5KB), не index.html — экономия токенов

---

## Доступ для агентов

| Агент | Как работает |
|-------|-------------|
| **Claude Code** | Edit data.json → git commit → git push |
| **Claude Desktop / Cowork** | Читает raw JSON с GitHub, предлагает изменения |
| **Codex** | Напрямую через git |

---

## Контекст

BLR — подписочное AI-комьюнити. Ксения — Community Ops Manager.
Главная цель: churn 45% → 20% за 90 дней.
Подробный контекст: `/Users/sizovaka/Documents/AI_LAB/Projects/06_BLR/CLAUDE.md`
