# Claude Code — Стартовый промпт для Joe v2

## Контекст

Создаём MVP web-приложения для автоматизации откликов на вакансии.

**Клиент:** Andrey Kasyanov (Senior Reservoir Engineer)  
**Оператор:** Ксения (управляет процессом)

Приложенные файлы содержат полную спецификацию:
- `CLAUDE.md` — инструкции агента
- `JOE_V2_MVP_ARCHITECTURE.md` — архитектура, UI, бизнес-правила
- `CLIENT_SPACE/canonical_resume.md` — каноническое резюме
- `CLIENT_SPACE/JOE_Strategy_v2.md` — стратегия и ограничения
- `CLIENT_SPACE/JOE_Process_Letter_v2.md` — правила писем

---

## Задача

Создай MVP web-приложения Joe v2.

---

## Требования

### Стек
- Frontend: React + Tailwind CSS
- Backend: Python (FastAPI или Flask)
- БД: Google Sheets (gspread)
- AI: Claude API для генерации CV/Letter

### Экраны (5)
1. **Pipeline** — таблица вакансий со статусами, сортировка по статусам
2. **Карточка вакансии** — JD + контакт + fit assessment + флаги
3. **CV** — каноническое резюме с правками (track changes style), скачать PDF, копировать правки
4. **Letter** — опциональный ввод пожеланий + сгенерированное письмо, скачать PDF, копировать
5. **Dashboard** — простая статистика (всего/новые/подано/ответы)

### Модульная архитектура
```
/modules
  /cv       — CV tailoring logic
  /letter   — Letter generation (легко заменяемый)
  /scoring  — Fit assessment + flags
```

Letter Module должен быть изолирован — замена файлов в `/modules/letter/` не ломает остальное.

### Интеграции
- Google Sheets как единственная БД (читаем при загрузке, пишем при каждом действии)
- Claude API для генерации (CV tailoring, Letter generation, Fit assessment)

---

## С чего начать

1. Структура проекта (файлы, папки)
2. Настройка Google Sheets интеграции
3. Backend API endpoints
4. Первый экран: Pipeline (таблица)

---

## Важно

- Читай `CLAUDE.md` для правил агента
- Читай `JOE_V2_MVP_ARCHITECTURE.md` для UI и бизнес-логики
- Letter Module — plug-in, правила в отдельном файле
- Не изобретать факты в CV/Letter — только из канона
