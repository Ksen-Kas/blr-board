# Joe v2 — Пакет правок #1

Применить все правки по порядку. После завершения — git commit.

---

## КРИТИЧНЫЕ — BACKEND

### Статусы
1. Единый enum статусов в `models/job.py`:
   ```
   New, In Progress, Applied, Waiting, Response, Interview, No Response, Closed
   ```
   Frontend берёт из backend, не хардкодит.

### JD парсинг
2. Добавить сервис парсинга JD:
   - Использовать Jina Reader API: `https://r.jina.ai/{url}`
   - Fallback: поле для ручного ввода текста JD
   - Если парсинг не удался — показать сообщение и поле ввода

### Дубликаты
3. Проверка при добавлении вакансии:
   - URL exact match
   - Fuzzy: Company + Role + Region совпадают
   - Флаг `possible_duplicate: boolean`
   - В UI: маркер "Возможный дубль"

### Follow-up
4. Вычислять при загрузке:
   - Applied + 4 дня без ответа = `needs_followup: true`
   - Поле в модели Job

### Флаги — ИСПРАВИТЬ БАГ
5. Разрешённые флаги ТОЛЬКО:
   - `visa_required` (STOP) — США + явно требуется виза
   - `citizenship` (STOP) — требуется гражданство
   - `exp_gap` (WARNING) — часть опыта отсутствует
   - `junior_role` (WARNING) — ищут ≤5 лет
   - `strong_mismatch` (REVIEW) — другой тип роли

6. УДАЛИТЬ из scoring модуля:
   - `geo` — НЕ флаг, убрать полностью
   - `contractor` — НЕ существует, убрать

### Error handling
7. Logging в модулях CV/Letter/Scoring
8. Понятные сообщения ошибок (не "проверьте backend")

---

## ДАННЫЕ — EVENT LOG

9. Новый лист Google Sheets: `Events`
   ```
   job_id | timestamp | event_type | data (JSON)
   ```

10. event_type enum:
    ```
    status_change, touchpoint, follow_up_sent, cv_generated, letter_generated, note
    ```

11. Backend:
    - Модель Event
    - Auto-log при: смене статуса, генерации CV, генерации Letter
    - `POST /jobs/{id}/events` — ручное добавление касания
    - `GET /jobs/{id}/events` — история событий

12. Хранить дельту CV (не полное резюме):
    - Колонка `cv_changes` (JSON)
    - Формат: `{"summary": "изменение", "skills": ["изменение"], ...}`

---

## FRONTEND — PIPELINE

13. Добавить колонку "Days" — дней с подачи

14. Fit цвета:
    - Strong = зелёный (#22c55e)
    - Stretch = светло-зелёный (#86efac)
    - Warning (flags) = жёлтый (#eab308)
    - Mismatch/Stop = красный (#ef4444)

15. Маркер дубликата (если `possible_duplicate`)

16. Иконка 🔔 если `needs_followup`

17. Фильтр по статусу:
    - Dropdown в header таблицы
    - Опции: All, New, In Progress, Applied, etc.

18. Сортировка (клик на header колонки):
    - По статусу
    - По компании
    - По региону

19. Days to First Response — показывать в таблице (не только в карточке)

---

## FRONTEND — КАРТОЧКА ВАКАНСИИ

20. Источник (ссылка):
    - Переместить наверх
    - Показывать только домен (energyjobsearch.com)
    - Полная ссылка — по клику или hover

21. Timeline — переместить наверх карточки

22. Статус — переделать UX:
    - Dropdown с явным chevron (▼)
    - Или badge + click
    - Не просто текст-ссылка

23. Секция "История касаний":
    - Timeline всех событий из Events
    - Кнопка "+ Касание" → форма (дата, канал, направление, заметка)

24. Кнопки — упростить:
    - Убрать кнопку Back (есть breadcrumb ← Pipeline)
    - Одна primary: [Prepare Application →] зелёная
    - Secondary outline: [Evaluate Fit], [Letter Only]
    - Порядок: primary слева, secondary справа

---

## FRONTEND — CV ЭКРАН

25. Убрать "Step 1 of 2" (или заменить на subtle progress bar)

26. Убрать дублирование заголовка (breadcrumb достаточно)

27. Добавить рекомендацию Joe:
    - "Tailoring рекомендуется" или "Канон подходит как есть"
    - На основе scoring

28. Две кнопки выбора:
    - [Использовать канон] — outline
    - [Tailor CV →] — primary

29. После tailoring — отображение:
    - Левая панель: текст с diff (подсветка изменений)
    - Правая панель: PDF preview
    - Или: styled view как оригинальное резюме + подсветка изменений

30. PDF генерация по шаблону:
    - Формат как оригинальное резюме (см. canonical PDF)
    - Не markdown/plain text

31. Кнопки после tailoring:
    - Порядок: [Next: Letter →] primary, [Re-tailor] secondary
    - Убрать Back to Card (есть breadcrumb)

32. Re-tailor:
    - Клик → модалка/поле "Что изменить?"
    - Кнопки: Отмена / Применить

---

## FRONTEND — ОБЩЕЕ

33. Все кликабельные элементы → `cursor: pointer`

34. Hover states на всех интерактивных элементах

35. Навигация: после Letter назад → карточка вакансии (не CV)

36. Breadcrumbs везде (уже есть, сохранить)

---

## НА БУДУЩЕЕ (добавить в PROGRESS.md → TODO)

- Визуальный flow (stepper/progress bar)
- Сохранение версий CV (история tailoring)
- Русское резюме (готовое, не tailoring)
- Dashboard доработки
- Reapply flow (новая подача на ту же вакансию)
- Telegram бот интеграция

---

## ПОСЛЕ ПРИМЕНЕНИЯ

1. `git add .`
2. `git commit -m "fix: corrections pack 1 — pipeline, cards, CV, events"`
3. Обновить PROGRESS.md
4. Добавить инсайты в LESSONS.md если есть
