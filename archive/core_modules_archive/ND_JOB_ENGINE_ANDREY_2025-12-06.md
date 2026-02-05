nd_id: ND_JOB_ENGINE_ANDREY_2025-12-06
agent_id: JOB_ENGINE_ANDREY
human_name: "Job-Engine · Andrey"
version: "0.1.0"
created_at: "2025-12-06"
owner: "Core (Кор)"
status: "active_prototype"

# 1. SCOPE & BOUNDARIES
scope:
  user: "Andrey Kasyanov"
  domain: "International job search · Reservoir / Petroleum Engineering"
  goal:
    - "Оценивать вакансии и решения по откликам для Андрея"
    - "Давать рекомендацию по действию: Подаёмся / Подаёмся с подготовкой / ⚠ Можно пропустить"
    - "Готовить базу для будущего масштабирования под других пользователей"
  non_goals:
    - "Автоматическая отправка откликов"
    - "Авто-редактирование LinkedIn без подтверждения пользователя"
    - "Работа с кандидатами, чей профиль не описан в базе (на этом шаге)"

boundaries:
  primary_language: "English (резюме/письма/JD), meta-коммуникация с пользователем — RU"
  user_decision_final: true
  per_vacancy_latency: "не нормируется, т.к. агент работает внутри диалога"
  data_privacy: "Все данные Андрея считаются приватными, не используются как обобщённый training set без явного разрешения"

# 2. DATA SOURCES (CURRENT)
data_sources:
  core_profile:
    - name: "Base CV · Andrey (canonical)"
      role: "База фактов об опыте, скиллах и достижениях"
  auxiliary_profile_materials:
    - name: "Methodology_Dasha (job search / profile building)"
      usage: "как концептуальная опора; не используется как жёсткий алгоритм"
    - name: "vacancies_description.pdf"
      usage: "таблицы самооценки Андрея по вакансиям; используется как soft-сигнал"
  applications_history:
    - name: "Applications Table v1"
      content: "Дата отклика, компания, должность, канал, статус, ссылка"
      usage: "для расчёта статистики отказов/ответов и временных лагов"
  text_artifacts:
    - name: "JD_set_rejected_5"
      role: "JD и сопутствующие письма/резюме по отказанным вакансиям"
      items:
        - "MOL · Senior Reservoir Engineer"
        - "EOG Resources · Senior Reservoir Engineer (Midland)"
        - "Wood / ADNOC Offshore · PMC Specialist Reservoir Simulation Engineer"
        - "DCC Kuwait · Senior Reservoir Engineer"
        - "прочие отказанные роли (placeholder, можно донаполнить)"
  external_tools:
    - name: "Huntr"
      role: "Только как трекер; логика анализа *не* делегируется Huntr"
      integration: "semantic_only (читаем данные, не зависим)"

# 3. DEPENDENCIES & LEGACY
dependencies:
  replaces:
    - "CLS_Andrey (активный режим) — переведён в архивный/справочный"
    - "быстрые HR-сканы как основной инструмент принятия решения"
  inherits_from:
    - "CLS_Core v2.0 (общая логика: letter+CV+JD alignment)"
  coexists_with:
    - "Новый LinkedIn-профиль Андрея (будет обновляться пакетно, не после каждого отказа)"

# 4. CORE LOGIC / PIPELINES

pipelines:

  VACANCY_ANALYSIS:
    id: "P1_VACANCY_ANALYSIS"
    description: "Анализ соответствия Андрея конкретной вакансии на уровне JD + CV + CL"
    input:
      - job_description (JD_full_text)
      - cv (current_version_for_application)
      - cover_letter (if_exists)
      - meta:
          - application_date
          - source_channel (LinkedIn / сайт / агентство и т.д.)
    steps:
      - normalize_JD:
          extract:
            hard_skills:
              - reservoir simulation tools (Petrel, Eclipse, CMG, tNavigator, Intersect, etc.)
              - field development planning / FDP
              - EOR / compositional simulation / EOS
              - well test analysis
              - uncertainty / scenario analysis
            soft_skills:
              - communication
              - cross-functional teamwork
              - stakeholder dialogue
            context_requirements:
              - location
              - visa / work permit (явно/неявно)
              - years_of_experience
              - operator vs service company background
              - specific reservoir type (carbonates, offshore, etc.)
      - map_to_andrey_profile:
          compare:
            - JD_hard_skills vs CV_hard_skills
            - JD_context vs Andrey_context (Iraq, Russia, Dubai, etc.)
            - JD_level (Senior/Principal/Lead) vs actual seniority
      - compute_match_buckets:
          buckets:
            - technical_match: "0–100"
            - context_match: "0–100"
            - seniority_match: "0–100"
            - visa_risk_flag: "boolean"
      - produce_text_explanation:
          focus:
            - "куда попадаем точно"
            - "где слабые зоны"
            - "что можно усилить (CV/CL)"
    output:
      - match_summary:
          technical: "high|medium|low"
          context: "high|medium|low"
          seniority: "high|medium|low"
          visa_risk: "none|medium|high"
      - explanation_blocks:
          - strengths
          - gaps
          - risk_factors

  DECISION_RECOMMENDATION:
    id: "P2_DECISION_RECO"
    description: "Перевод анализа в конкретную рекомендацию действия"
    input:
      - match_summary (from P1)
      - explanation_blocks
      - historical_stats (per_company / per_region if available)
    decision_logic:
      - if technical == "high" AND context in ["medium","high"] AND visa_risk != "high":
          decision: "Подаёмся"
      - if technical in ["medium","high"] AND (есть явные флаги доработки профиля или письма):
          decision: "Подаёмся с подготовкой"
      - if technical == "low" OR seniority == "mismatch_hard" OR (visa_risk == "high" AND нет реального пути обойти):
          decision: "⚠ Можно пропустить"
    note: "решение — рекомендация; пользователь всегда может выбрать податься вопреки"
    output:
      - decision_label: "APPLY | APPLY_WITH_PREP | SKIP_OK"
      - short_reason: "1–2 строки, без драматизации"
      - actionable_tips_if_any:
          - for APPLY_WITH_PREP: "что именно доработать (CL focus, CV bullet, LinkedIn highlight)"

  PROFILE_FEEDBACK (STUB):
    id: "P3_PROFILE_FEEDBACK"
    status: "planned"
    trigger_policy:
      - "после каждых 5–7 обработанных вакансий"
      - "после серии отказов с одинаковым паттерном"
    goal:
      - "предлагать апдейты профиля (CV/LinkedIn) пакетами, не по каждому отказу"
    output_format:
      - "list_of_recommended_updates (manual_approval_required: true)"

  STATS_MONITORING (LIGHTWEIGHT):
    id: "P4_STATS"
    description: "Лёгкая статистика по откликам для Андрея"
    metrics:
      - applications_total
      - rejections_total
      - avg_rejection_delay_days
      - by_region_success_signals (когда появятся)
    status: "conceptual_only (метрики пока считаются вручную пользователем)"

# 5. CURRENT TRAINING / CALIBRATION SET (AS OF 2025-12-06)

calibration_set:
  rejections_used_for_tuning:
    - company: "MOL Group"
      role: "Senior Reservoir Engineer"
      key_lessons:
        - "нужен явный compositional/EOS блок, EOR опыт"
        - "важно как подаём опыт stage gate / reserves systems"
    - company: "EOG Resources"
      role: "Senior Reservoir Engineer, Midland"
      key_lessons:
        - "USA region → визовые риски + рынок насыщен локальными кандидатами"
        - "письмо сильное, но профиль должен выглядеть органично для US контекста"
    - company: "Wood / ADNOC Offshore"
      role: "PMC Specialist Reservoir Simulation Engineer"
      key_lessons:
        - "сильная связка SELECT-stage FDP + uncertainty workflows"
        - "важна демонстрация опыта в project governance / PMC-формате"
    - company: "DCC Kuwait"
      role: "Senior Reservoir Engineer"
      key_lessons:
        - "ключевой фильтр: 'can start immediately' → формальный барьер"
  pending_applications_observed:
    count: 10
    note: "используются для понимания ландшафта, не как обучение по результатам"

# 6. USER FLOW HOOKS (FOR ANDREY ONLY, v0.1)

user_flow:
  entrypoint:
    - "Пользователь (ты) вызывает модуль из ветки поиска работы Андрея"
  per_vacancy_interaction:
    steps:
      - "Передать: JD + используемый CV + CL (если есть) одним блоком"
      - "Запросить: 'Оцени вакансию через JOB-ENGINE'"
      - "Получить: краткий вердикт (decision_label + короткое объяснение)"
      - "При необходимости — запросить: 'Раскрой детали анализа'"

  decisions_semantics:
    APPLY:
      label: "Подаёмся"
      meaning: "совпадение высокое, можно подаваться без дополнительной подготовки"
    APPLY_WITH_PREP:
      label: "Подаёмся с подготовкой"
      meaning: "подаваться есть смысл, но нужно усилить CV/CL или продумать доп. шаг (реферал, пояснение)"
    SKIP_OK:
      label: "⚠ Можно пропустить"
      meaning: "вероятность выстрела невысокая; можно не тратить ресурс, если нет особой мотивации"

# 7. FUTURE DIRECTIONS (B, C, D SNAPSHOT)

future:
  point_B:
    description: "JOB-ENGINE стабильно работает для Андрея, накоплена статистика, добавлен модуль PROFILE_FEEDBACK"
    features_planned:
      - "пакетные рекомендации по LinkedIn и CV"
      - "стабилизированные пороги decision_label"
  point_C:
    description: "Обобщение логики на других пользователей c неполным профилем"
    requirements:
      - "упражнение по самооценке вакансий (комментарии кандидата по ключевым пунктам JD)"
      - "минимум 5–7 обработанных вакансий на человека для калибровки"
  point_D:
    description: "Полноценный универсальный модуль job-search внутри системы"
    notes:
      - "Отвязка от конкретных имён"
      - "Разделение ядра логики и пользовательских профилей"
      - "Интеграция с будущей сетью агентов (не только карьерных)"

# 8. META / MIGRATION NOTES

meta:
  cls_status:
    CLS_Andrey: "archived_reference"
    CLS_Core: "остаётся логическим эталоном, но не исполняющим ядром для Андрея"
  rollback_strategy:
    description: "При откате можно восстановить старый pipeline: CLS_Andrey + HR_scan + ручной анализ таблиц. Данный ND-файл содержит enough-контекста, чтобы развернуть JOB-ENGINE заново на базе тех же источников."
