# CLAUDE.md — BLR Board

Интерактивная доска задач BLR-комьюнити. GitHub Pages + JSON.

---

## Архитектура

```
blr-board/
├── index.html   ← UI (НЕ ТРОГАТЬ без запроса Ксении)
├── data.json    ← данные доски (агент редактирует ТОЛЬКО этот файл)
└── CLAUDE.md    ← этот файл
```

**Хостинг:** GitHub Pages → `https://ksen-kas.github.io/blr-board/`
**Репо:** `Ksen-Kas/blr-board` (private)
**Деплой:** автоматический при push в main (Pages обновляется ~30 сек)

---

## Как агенту обновить доску

### Принцип: минимум токенов, максимум точности

1. **Прочитай `data.json`** — это единственный источник правды
2. **Измени нужные поля** через Edit tool (точечно, не перезаписывай весь файл)
3. **Обнови поле `"updated"`** на текущую дату (YYYY-MM-DD)
4. **Сделай git commit + push** в main

```bash
cd /Users/sizovaka/Documents/AI_LAB/GitHub/blr-board
git add data.json
git commit -m "update: краткое описание"
git push
```

Через ~30 сек изменения появятся на сайте.

### Что можно менять в data.json

| Секция | Что | Пример |
|--------|-----|--------|
| `fire` | Горящие задачи (макс 5-7) | Добавить/убрать/отметить done |
| `tasks` | Задачи по категориям | Добавить задачу, сменить priority |
| `goals` | Цели Юли | Обновить формулировки |
| `waiting` | Что ждём от кого | Добавить/убрать пункт |
| `metrics` | Метрики | Обновить val и sub |
| `horizons` | 30/60/90 дней | Обновить items |
| `updated` | Дата обновления | Всегда ставить текущую |

### Структура задачи

```json
{
  "id": "t22",
  "title": "название задачи",
  "sub": "описание / контекст",
  "tags": [["red","горит"], ["amber","эта неделя"]],
  "done": false,
  "priority": "fire|high|mid|low"
}
```

**ID-конвенция:** `f1-f99` для fire, `t1-t999` для tasks.
**Цвета тегов:** `red`, `amber`, `teal`, `purple`, `gray`.

### Чего НЕ делать

- Не редактировать `index.html` без явного запроса
- Не менять структуру JSON (ключи, вложенность)
- Не добавлять HTML в текстовые поля
- Не пушить в другие ветки — только main

---

## Экономия токенов

**При чтении:** читай только `data.json` (~3KB), не index.html (~8KB).

**При обновлении:** используй Edit tool для точечных изменений:
```
Edit: data.json
old: "done": false    (для конкретной задачи)
new: "done": true
```

**НЕ перечитывай** index.html каждый раз — он не меняется.

---

## Доступ для разных агентов

| Агент | Как обновляет |
|-------|--------------|
| **Claude Code (CLI)** | Edit `data.json` → `git commit` → `git push` |
| **Claude Desktop / Cowork** | Через gh CLI или API: читает raw JSON, предлагает изменения |
| **Codex** | Напрямую через git в репо |

**Путь к локальной копии:** `/Users/sizovaka/Documents/AI_LAB/GitHub/blr-board/`

---

## Контекст проекта

BLR — подписочное AI-комьюнити. Ксения — Community Ops Manager.
Главная цель: churn 45% → 20% за 90 дней.
Подробный контекст: `/Users/sizovaka/Documents/AI_LAB/Projects/06_BLR/CLAUDE.md`
