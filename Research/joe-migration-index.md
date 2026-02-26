# Индекс материалов Joe — для миграции GPT → Claude

**Цель:** перенести действующего агента Joe (JOE_APPLY) из GPTs в Claude/Cursor.  
**Дата:** 2026-02-22  
**Охват:** ~40 файлов в AI_LAB + KnowledgeBase

---

## Статус файлов по приоритету миграции

| Приоритет | Смысл |
|-----------|-------|
| 🔴 Критично | Без этого Claude не работает как Joe |
| 🟡 Важно | Контекст, который определяет качество |
| 🟢 Справочно | История, архив, дублирование |

---

## 1. Системный промпт (Runtime Core)

### `KnowledgeBase/03_ai_make/joe/joe_instructions_gpts.md`
🔴 **Критично**

**JOE_APPLY v1.6 — финальная версия промпта**, написанного для GPTs.  
**Ценность для миграции:** это текущая рабочая инструкция агента. Нужно взять за основу и адаптировать под Claude/Cursor:
- убрать GPT-специфичные ноты («paste into GPTs → Instructions»),
- сохранить всю логику: роль, OUT OF SCOPE, Control Header, CANON SYSTEM, VACANCY INPUT, ANTI-DRIFT GUARD, DONE CRITERIA,
- сохранить блок LETTER OPENING RULE (v1.6 patch) — он финальный и важный.

---

## 2. Ядро: роль, правила, IO, стиль, валидация

Все эти файлы — **модульная декомпозиция** того же промпта v1.6. Они более подробны и структурированы, чем компактная GPTs-версия.

### `AI_LAB/00_inbox/core/JOE_CORE_ROLE_AND_SCOPE.md`
🔴 **Критично**

Определяет: кто такой Joe, что он производит (4 типа deliverables), что вне скоупа, клиент-агностичная модель.  
**Ключевое:** секция **"Dependency Model"** — агент не зависит от API/модели, работает на правилах. Это принципиально для перехода с GPT на Claude.

### `AI_LAB/00_inbox/core/JOE_RULES_AND_CONSTRAINTS.md`
🔴 **Критично**

Все жёсткие правила: Canon System (v1/v2), Data Authority, No-Invention Rule, Base CV Routing, Vacancy Input Rules, CV Architecture Rules, Anti-Drift Guard, Done Criteria.  
**Это сердце ограничений агента.** Полностью переносится без изменений.

### `AI_LAB/00_inbox/core/JOE_IO_AND_MODES.md`
🔴 **Критично**

Протокол ввода/вывода: Control Header (обязательный первый блок каждого ответа), типы входных данных, все 6 MODE: BUNDLE / CV_TAILOR / LETTER / FORM / MESSAGE / CANON_CHECK.  
**Ценность:** точное описание того, что делает агент при каждом сценарии использования.

### `AI_LAB/00_inbox/core/JOE_STYLE_CANON.md`
🔴 **Критично**

Стиль всех deliverables: язык (executive English), голос (calm/confident/adult), запрещённые HR-клише (hard ban list), структура письма (4 параграфа), правила CV-адаптации, микро-шаблоны открытий/закрытий писем.  
**Ценность:** без этого файла Claude будет писать «в своём стиле», теряя характер Joe.

### `AI_LAB/00_inbox/core/JOE_VALIDATION_LAYER.md`
🔴 **Критично**

Обязательный слой для любой работы с CV: формат CANON CHECK (OK/WARN/FAIL/BLOCKED), правила вызова, Letter Opening Rule (v1.6), Letter Delivery Format Guard, CV_TAILOR Delivery Format Guard.  
**Ценность:** гарантирует что Claude не будет изобретать факты и будет явно маркировать проблемы.

---

## 3. История и архитектура (для понимания контекста)

### `AI_LAB/00_inbox/JOE_Snapshot/_RAW_SPEC.md`
🟡 **Важно**

Самый полный нарратив о происхождении Joe: CV-LAB → Job Engine → Joe, структура слоёв (JO_Core, Profile Scanner, Decision Layer, Validation Layer), принципы, воркфлоу Ward → CV-LAB → Joe, ограничения, стиль.  
**Ценность для миграции:** помогает понять, какие части Joe сейчас «активны» (JOE_APPLY), а какие исторически зафиксированы (Decision Layer, Joe Script).  
Предлагает готовую файловую структуру агента (6 файлов: JOE_OVERVIEW, JOE_PRINCIPLES, JOE_WORKFLOWS, JOE_CONSTRAINTS, JOE_TONE_STYLE, JOE_CVLAB_CORE, JOE_SYSTEM_ARCHITECTURE).

### `AI_LAB/00_inbox/core/JOE_ARCHIVE_HISTORY.md`
🟡 **Важно**

Документирует эволюцию: CV-LAB v1.0 (ONE-SHOT MENTOR / ATS_OPERATOR / HR-SCAN) → Ward препроцессор → Joe внутри Job Engine → JOE_APPLY v1.4 → v1.5 (GPT) → v1.6 (финал).  
**Ключевое для миграции:** секции «Versioned JOE_APPLY Instructions» и «Deprecated Forms» — чётко указывают, что устарело и что не нужно переносить (GPT-специфичные UI-ноты, ссылки на одного клиента).

---

## 4. Концепция ядра и снапшотов

### `KnowledgeBase/03_ai_make/joe/joe_kernel.md`
🟡 **Важно**

Концепция **Joe Kernel vs Joe Instance**: ядро агностично к человеку, контекст клиента подгружается через Space + Snapshot.  
**Ценность:** архитектурный принцип для Claude-реализации — один агент, много клиентов.  
Формула: **Joe-Andrey = Kernel + ANDREY Space + Snapshots.**

### `KnowledgeBase/03_ai_make/joe/joe_snapshot_rules.md`
🟡 **Важно**

Правила системы Core vs Snapshot: Core = неизменяемая логика, Snapshot = состояние на момент времени.  
**Ценность:** объясняет механизм восстановления и масштабирования Joe на других клиентов без изменения ядра.  
Три типа снапшотов: Canonical Resume Snapshot, Joe State Snapshot, Project Snapshot.

### `KnowledgeBase/03_ai_make/joe/joe_pipeline.md`
🟡 **Важно**

8-этапный пайплайн Joe для Андрея: условия запуска, анализ вакансии (go/no-go), адаптация CV, Cover Letter, Application Forms, Outreach, Трекинг, Итерации.  
**Ценность:** чёткое разделение — что делает Joe, что остаётся у оператора.

---

## 5. Документация продукта (GPTs-архитектура и онбординг)

### `KnowledgeBase/02_ai_agents/JOE GPTs.md`
🟡 **Важно**

Самый развёрнутый операционный документ: полный список задач поиска работы (9 блоков, 31 задача), таблица задача→инструмент, JOE_APPLY v1 Architecture, Client Onboarding (1 экран), файловая структура Knowledge, три слоя GPTs (Instructions/Knowledge/Chat), сравнение GPTs vs Cursor.  
**Ключевое для миграции:**
- Секция «Почему нельзя сделать "полного Джо" в GPTs» — обоснование текущего разделения JOE (стратегия) vs JOE_APPLY (исполнение).
- Секция «GPTs vs Cursor» — прямое сравнение с описанием файловой структуры Cursor-реализации.
- «Почему ранее плыл Джо» — диагноз проблем с GPT-реализацией.
- «Instructions: что туда класть» — руководство по написанию системного промпта для Claude.

### `KnowledgeBase/02_ai_agents/__Joe _ Project Documentation__.md`
🟡 **Важно**

Минимально достаточная структура репозитория Joe (5–6 файлов): README, PIPELINE, JOE_CORE, CANON, SNAPSHOTS, TOOLS.  
**Ценность:** готовая схема организации файлов для Claude/Cursor-реализации.

---

## 6. Дополнительные модули ядра (KnowledgeBase)

### `KnowledgeBase/03_ai_make/joe/joe_role_and_scope.md`
🟢 Справочно — дублирует `JOE_CORE_ROLE_AND_SCOPE.md`, русскоязычная версия с деталями дрейфа.

### `KnowledgeBase/03_ai_make/joe/joe_rules_and_constraints.md`
🟢 Справочно — дублирует `JOE_RULES_AND_CONSTRAINTS.md`.

### `KnowledgeBase/03_ai_make/joe/joe_style_canon.md`
🟢 Справочно — дублирует `JOE_STYLE_CANON.md`.

### `KnowledgeBase/03_ai_make/joe/joe_io_and_modes.md`
🟢 Справочно — дублирует `JOE_IO_AND_MODES.md`.

### `KnowledgeBase/03_ai_make/joe/joe_validation_layer.md`
🟢 Справочно — дублирует `JOE_VALIDATION_LAYER.md`.

### `KnowledgeBase/03_ai_make/joe/joe_andrey_space.md`
🟢 Справочно — Space: контекст работы Joe для Андрея. Нужен при запуске агента под конкретного клиента, не для ядра.

### `KnowledgeBase/03_ai_make/joe/joe_fact_check.md`
🟢 Справочно — протокол FACT_CHECK. Дополняет Validation Layer, можно включить в Knowledge-файлы.

---

## 7. Код и бот (AI_LAB)

### `AI_LAB/02_projects/02_Joe-Bot/` + `GitHub/joe-bot/`
🟢 Справочно

`joe.py` — загрузка системного промпта.  
`bot.py` — вызов `joe.evaluate()`, форматирование Telegram-сообщений.  
`main.py` — запуск бота.  
`job_search_bot_brief.md` — бриф: бот оценивает вакансии через Claude API.  
`joe_system_prompt.txt` — системный промпт в txt-формате (не найден на диске, возможно перемещён).

**Ценность для миграции:** код уже работает через Claude API — значит, техническая обвязка частично готова. `bot.py` и `joe.py` показывают, как вызывается агент программно.

---

## 8. Системный контекст и публикации

### `AI_LAB/README.md`
🟢 Справочно

Описание системы двух файлов (JOE_PROCESS_MODEL + ANDREY_OBJECT_PROFILE), инструкция перезапуска в новой ветке ChatGPT, описание ролей инструментов (ChatGPT/Claude/Perplexity).  
**Ценность:** показывает текущий workflow — его нужно будет обновить под Claude после миграции.

### `AI_LAB/01_sources/_context.md`
🟢 Справочно

Общий контекст Ксении: структура мультиагентной системы (Joe, CLS, HR-Scan, Kor, Артём, Mia), методология 5 фаз, структура файлов.

### `AI_LAB/GitHub/Publications/books/multi-agent-tutorial.html`
🟢 Справочно

Публикация: Joe в мульти-агентном пайплайне (резюме → Joe, рыночные вопросы → Deep Research).

---

## 9. Архивы (пропустить при миграции)

### `AI_LAB/00_inbox/core-system-archive copy/Joe/`
🟢 Дублирует `00_inbox/core/` — те же файлы, более старая версия. При конфликте приоритет у `00_inbox/core/`.

---

## Что нужно для миграции: минимальный набор

```
1. joe_instructions_gpts.md   ← системный промпт (адаптировать под Claude)
2. JOE_RULES_AND_CONSTRAINTS.md  ← правила и ограничения
3. JOE_IO_AND_MODES.md           ← протокол ввода/вывода
4. JOE_STYLE_CANON.md            ← стилевой канон
5. JOE_VALIDATION_LAYER.md       ← слой валидации
6. [CANON_RESUME клиента]        ← единственный источник фактов (отдельно для каждого клиента)
```

Дополнительно для понимания системы:
- `_RAW_SPEC.md` — полная история и архитектура
- `JOE GPTs.md` — диагноз проблем и сравнение с Cursor
- `joe_kernel.md` + `joe_snapshot_rules.md` — модель масштабирования

---

## Ключевые инсайты для адаптации под Claude

1. **Агент не зависит от модели.** `JOE_CORE_ROLE_AND_SCOPE.md` явно говорит: «The agent does not depend on a specific API or model.» Claude — валидный хост.

2. **GPT-специфичные части надо убрать:** ноты «paste into GPTs → Instructions», ссылки на GPTs Knowledge-слой, упоминание конкретного клиента (Андрей) в системном промпте.

3. **Control Header остаётся.** MODE / CANON / CLIENT / TARGET / BASE_CV — архитектурно важная часть, работает в любом контексте.

4. **Главная проблема GPT-версии** (из `JOE GPTs.md`): «часть ядра жила в истории чата, часть — в файлах, часть — в голове оператора». В Claude/Cursor это решается файловым контекстом.

5. **Три слоя GPTs → три слоя Cursor:**
   - Instructions (поведение) → системный промпт Claude
   - Knowledge (файлы) → файлы в рабочей директории / project knowledge
   - Chat (сессия) → текущий разговор

6. **Deprecated не переносить:** любые CLS_* / CV-LAB промпты как отдельные агенты, ранние JOE_APPLY v1.4/v1.5 с GPT-UI-нотами, Andrey-специфичные части в системном промпте.
