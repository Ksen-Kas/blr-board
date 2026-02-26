# Список материалов про Joe / Джо / CV lab

Поверхностный обход: **AI_LAB** и **KnowledgeBase** (поиск по Joe, Джо, CV lab). В KnowledgeBase исключены папки `logs_gpt` и `logs_tg`.  
Краткая версия (без разбивки KB): `02_projects/list-joe-cvlab-materials.md`.

---

## 1. Корень проекта (AI_LAB)

| Файл | Содержание |
|------|------------|
| `README.md` | JOE System: как думает и работает Джо, пайплайн, перезапуск в ChatGPT, запуск для клиента |

---

## 2. Контекст и источники (AI_LAB)

| Файл | Содержание |
|------|------------|
| `01_sources/_context.md` | Joe (Job Engine) — аналитическая поддержка поиска работы |

---

## 3. Проект Joe-Bot (код и брифы) (AI_LAB)

| Файл | Содержание |
|------|------------|
| `02_projects/02_Joe-Bot/bot.py` | Импорт и вызов `joe.evaluate()`, форматирование сообщений Joe |
| `02_projects/02_Joe-Bot/main.py` | Запуск «Joe Bot», регистрация хендлеров |
| `02_projects/02_Joe-Bot/joe.py` | Загрузка системного промпта Joe |
| `02_projects/02_Joe-Bot/job_search_bot_brief.md` | Бриф: бот оценивает вакансии через Claude API (Joe), маппинг из `joe.evaluate()`, модуль joe.py |
| `02_projects/02_Joe-Bot/joe_system_prompt.txt` | Системный промпт Joe (JOE_CORE_ROLE, JOE_RULES, JOE_VALIDATION_LAYER, JOE_STYLE_CANON) |

**Дубликат в GitHub:** папка `GitHub/joe-bot/` — те же файлы: `bot.py`, `main.py`, `joe.py`, `job_search_bot_brief.md`, `joe_system_prompt.txt`.

---

## 4. Ядро Joe (inbox/core) (AI_LAB)

| Файл | Содержание |
|------|------------|
| `00_inbox/core/JOE_ARCHIVE_HISTORY.md` | Эволюция Joe: из агента **CV-LAB** для Андрея Касьянова → Job Engine; Ward → CV-LAB → Joe; Joe Script, JOE_APPLY |
| `00_inbox/core/JOE_CORE_ROLE_AND_SCOPE.md` | Имя агента Joe / Джо / JOE_APPLY, scope, дрейф |
| `00_inbox/core/JOE_RULES_AND_CONSTRAINTS.md` | Правила и ограничения Joe |
| `00_inbox/core/JOE_IO_AND_MODES.md` | Ввод/вывод и режимы, ссылки на JOE_* |
| `00_inbox/core/JOE_VALIDATION_LAYER.md` | Валидационный слой, ссылка на JOE_STYLE_CANON |
| `00_inbox/core/JOE_STYLE_CANON.md` | Стилевой канон Joe |

---

## 5. Снапшот и сырая спецификация Joe (AI_LAB)

| Файл | Содержание |
|------|------------|
| `00_inbox/JOE_Snapshot/_RAW_SPEC.md` | Полное описание: Joe (Джо) как карьерный движок из **CV-LAB**; наследие CV-LAB, эволюция CLS/CV-LAB → Джо, Ward → CV-LAB → Джо, Job Engine, ограничения, CV LAB как предшественник Joe |

---

## 6. Архив (копия) — core-system-archive copy/Joe (AI_LAB)

| Файл | Содержание |
|------|------------|
| `00_inbox/core-system-archive copy/Joe/core/JOE_ARCHIVE_HISTORY.md` | Та же история: CV-LAB → Joe, Ward → CV-LAB → Joe |
| `00_inbox/core-system-archive copy/Joe/core/JOE_CORE_ROLE_AND_SCOPE.md` | Joe / Джо / JOE_APPLY |
| `00_inbox/core-system-archive copy/Joe/core/JOE_RULES_AND_CONSTRAINTS.md` | — |
| `00_inbox/core-system-archive copy/Joe/core/JOE_IO_AND_MODES.md` | — |
| `00_inbox/core-system-archive copy/Joe/core/JOE_VALIDATION_LAYER.md` | — |
| `00_inbox/core-system-archive copy/Joe/core/JOE_STYLE_CANON.md` | — |
| `00_inbox/core-system-archive copy/Joe/JOE_Snapshot/_RAW_SPEC.md` | Та же _RAW_SPEC про Joe и CV-LAB |

---

## 7. Публикации (AI_LAB)

| Файл | Содержание |
|------|------------|
| `GitHub/Publications/books/multi-agent-tutorial.html` | Туториал по мульти-агентам: Joe + CLS + HR-Scan, агент Joe в пайплайне (резюме → Joe, вопросы по рынку → Deep Research) |

---

## 8. Obsidian (AI_LAB)

| Файл | Содержание |
|------|------------|
| `.obsidian/workspace.json` | Ссылки на открытый файл `GitHub/joe-bot/job_search_bot_brief.md` |

---

## 9. KnowledgeBase (вне logs_gpt и logs_tg)

Путь базы: `/Users/sizovaka/Documents/KnowledgeBase`. Папки `logs_gpt` и `logs_tg` в поиск не входили.

### 9.1 Индекс и папка joe (03_ai_make)

| Файл | Содержание |
|------|------------|
| `03_ai_make/INDEX.md` | Раздел «joe/ — Карьерный агент Joe (11 файлов)»: перечень joe_*.md, JOE_Apply/STYLE_CANON |
| `03_ai_make/joe/joe_role_and_scope.md` | JOE_CORE_ROLE_AND_SCOPE; агент Joe / Джо / JOE_APPLY; дрейф |
| `03_ai_make/joe/joe_rules_and_constraints.md` | JOE_RULES_AND_CONSTRAINTS |
| `03_ai_make/joe/joe_style_canon.md` | JOE_STYLE_CANON |
| `03_ai_make/joe/joe_io_and_modes.md` | JOE_IO_AND_MODES, ссылки на JOE_* |
| `03_ai_make/joe/joe_validation_layer.md` | JOE_VALIDATION_LAYER, JOE_STYLE_CANON |
| `03_ai_make/joe/joe_instructions_gpts.md` | JOE_APPLY v1.6 — системный промпт для GPTs |
| `03_ai_make/joe/joe_kernel.md` | Ядро Joe (Kernel vs Instance), Joe-Andrey |
| `03_ai_make/joe/joe_pipeline.md` | Пайплайн Joe для Андрея, 8 этапов, Joe = execution engine |
| `03_ai_make/joe/joe_snapshot_rules.md` | Core vs Snapshot в системе Joe, Joe State Snapshot |
| `03_ai_make/joe/joe_andrey_space.md` | Space: контекст работы Joe, сверка с Space |
| `03_ai_make/joe/joe_fact_check.md` | Протокол FACT_CHECK для Joe |

### 9.2 Агенты и документация (02_ai_agents)

| Файл | Содержание |
|------|------------|
| `02_ai_agents/__Joe _ Project Documentation__.md` | Joe / Project Documentation: назначение, пайплайн, JOE_CORE, восстановление и перенос Joe |
| `02_ai_agents/JOE GPTs.md` | JOE GPTs: пайплайн, JOE_APPLY v1, onboarding, «полный Джо» vs JOE_APPLY, почему «плыл Джо» |

---

## Краткая навигация по темам

| Тема | Где искать |
|------|------------|
| **Joe как агент / бот (код)** | AI_LAB: `02_projects/02_Joe-Bot/`, `GitHub/joe-bot/` |
| **Правила и роли Joe (JOE_*)** | AI_LAB: `00_inbox/core/`, архив Joe; **KB:** `03_ai_make/joe/` |
| **История: CV-LAB → Joe, Джо** | AI_LAB: `JOE_ARCHIVE_HISTORY.md`, `JOE_Snapshot/_RAW_SPEC.md` |
| **Системный промпт Joe** | AI_LAB: `joe_system_prompt.txt`; **KB:** `03_ai_make/joe/joe_instructions_gpts.md` |
| **Joe в мульти-агентном контексте** | AI_LAB: `01_sources/_context.md`, `multi-agent-tutorial.html`, README |
| **Joe в KnowledgeBase** | KB: `02_ai_agents/` (документация, GPTs), `03_ai_make/joe/` (ядро, пайплайн, правила) |

---

*Итого: ~25 файлов в AI_LAB + 14 файлов в KnowledgeBase (без logs_gpt и logs_tg).*
