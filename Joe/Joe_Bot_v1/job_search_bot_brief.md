# Job Search Bot — MVP Technical Brief
> Передай этот файл в Cursor agent mode. Он содержит всё для сборки MVP без дополнительных вопросов.

---

## Контекст

Система автоматизации job search для Senior/Principal Reservoir Engineer (Middle East рынок).  
Клиент находит вакансии → кидает в Telegram → бот оценивает через Claude API (Joe) → пишет в Google Sheets.

---

## Стек

| Компонент | Технология |
|-----------|-----------|
| Бот | Python, python-telegram-bot |
| AI оценка | Claude API (claude-sonnet-4-5 или новее) |
| База данных | Google Sheets API v4 |
| Парсинг ссылок | httpx + BeautifulSoup4 |
| Хостинг | [ЗАПОЛНИ: Railway / Render / VPS] |
| Планировщик | APScheduler (внутри бота) |

---

## Переменные окружения (.env)

```
TELEGRAM_BOT_TOKEN=        # от @BotFather
TELEGRAM_CHAT_ID=          # ID чата где живёт бот
ANTHROPIC_API_KEY=         # Claude API key
GOOGLE_SHEET_ID=           # ID Google Sheets (из URL)
GOOGLE_CREDENTIALS_JSON=   # путь к service account JSON
```

---

## Структура проекта

```
job-search-bot/
├── main.py              # точка входа, запуск бота
├── bot.py               # handlers Telegram
├── joe.py               # логика оценки через Claude API
├── sheets.py            # работа с Google Sheets
├── parser.py            # парсинг ссылок на вакансии
├── scheduler.py         # ежедневные напоминалки
├── config.py            # загрузка .env
├── requirements.txt
└── .env
```

---

## Схема данных — Google Sheets

Лист называется `Pipeline`. Колонки в строгом порядке (строка 1 — заголовки):

```
Company | Role | Region | Seniority | Operator vs Contractor |
Status | Submission # | Reapply Reason |
Applied Date | Follow-up 1 | Follow-up 2 |
Response Date | Days to First Response |
Source | Channel | Role Fit | Stop Flags |
Contact | CV | CL | Comment
```

**Типы данных:**
- Даты: строка формата `DD.MM.YY`
- `Submission #`: целое число, по умолчанию `1`
- `Status`: одно из `New | Applied | Screening req | HR Screen | Interview | [No response] | [Rejected]`
- `Role Fit`: одно из `Strong | Partial | Stretch`
- `Stop Flags`: текст, значения через запятую из `level | geo | visa | contractor | exp`, или пусто
- `Operator vs Contractor`: `Operator` или `Contractor`
- `Channel`: `LinkedIn | Portal | Recruiter | Referral`

---

## Модуль: bot.py — Telegram handlers

### Входящие сообщения

Бот должен обрабатывать два типа входа:

**1. Ссылка на вакансию**
- Если URL содержит `linkedin.com` → ответить:
  ```
  LinkedIn не читается напрямую. Вставь текст JD сюда — и я оценю.
  ```
- Если другой URL → вызвать `parser.parse_url(url)` → передать текст в `joe.evaluate(jd_text, source_url)`

**2. Текст JD (любое сообщение длиннее 200 символов)**
- Передать в `joe.evaluate(jd_text, source=None)`

### Inline кнопки после оценки

После вывода оценки Joe показать две кнопки:
```
[✅ Добавить в трекер]  [❌ Пропустить]
```

При нажатии `✅ Добавить в трекер`:
- Проверить дубль через `sheets.check_duplicate(company, role)`
- Если дубль найден — спросить:
  ```
  ⚠️ Эта вакансия уже в трекере (Company / Role).
  Это повторная подача?
  [Да, повторная подача]  [Нет, отмена]
  ```
- Если `Да` → запросить причину текстом → записать с `Submission # = N+1`
- Если `Нет` → не записывать, сообщить "Ок, пропускаем"
- Если дубля нет → записать новую строку через `sheets.add_row()`

---

## Модуль: joe.py — Оценка вакансии

### Системный промпт для Claude API

```python
SYSTEM_PROMPT = """
Ты — Joe, алгоритм первичной оценки вакансий для Senior/Principal Reservoir Engineer.

Клиент: Andrey Kasyanov
Профиль: 18 лет опыта, Senior/Principal RE, специализация карбонаты, симуляция, field development.
Целевой рынок: UAE, Saudi Arabia, Qatar. Только операторы (ADNOC, Aramco, QatarEnergy, Shell ME, BP ME, TotalEnergies ME).
Инструменты: Eclipse, tNavigator, Petrel RE, Python.
Текущее место: LUKOIL Mid East, West Qurna-2, Ирак (employed, не срочный поиск).

Стоп-факторы (проверяй явно, не блокируй — только сигнализируй):
- level: JD требует Junior или Mid (< 10 лет)
- geo: локация за пределами UAE/KSA/Qatar
- visa: требуется гражданство или local hire
- contractor: сервисная компания или консалтинг
- exp: требуемый опыт явно не совпадает (< 10 или > 25 лет)

Шаблон CV: стандартный (карбонаты, симуляция, field development, waterflood management, $1B CAPEX оптимизация).

Твой вывод — ТОЛЬКО структурированный блок ниже. Никакого лишнего текста.
"""

OUTPUT_FORMAT = """
Формат ответа (строго):

COMPANY: [название или Unknown]
ROLE: [название роли]
REGION: [страна/город]
SENIORITY: [Senior / Principal / Other]
OPERATOR: [Operator / Contractor]
CHANNEL: [LinkedIn / Portal / Recruiter / Other]

STOP_FLAGS: [level, geo, visa, contractor, exp через запятую — или NONE]
ROLE_FIT: [Strong / Partial / Stretch]
CV_READY: [YES / NEEDS_WORK]
CV_NOTE: [одна строка — почему нужна доработка, или пусто]

SUMMARY: [2-3 строки свободного текста — ключевые совпадения или расхождения]
"""
```

### Функция evaluate()

```python
def evaluate(jd_text: str, source_url: str = None) -> dict:
    # Вызвать Claude API с SYSTEM_PROMPT + OUTPUT_FORMAT + jd_text
    # Распарсить ответ в словарь
    # Вернуть dict с полями: company, role, region, seniority, operator,
    #   channel, stop_flags, role_fit, cv_ready, cv_note, summary
```

### Форматирование вывода в Telegram

```python
def format_telegram_message(result: dict) -> str:
    # Иконка статуса:
    # stop_flags == NONE → 🟢 Clean
    # stop_flags содержит флаги но role_fit != Stretch → 🟡 Check  
    # stop_flags содержит флаги и role_fit == Stretch → 🔴 Flags

    # Шаблон:
    """
{icon} {company} — {role} ({region})
Role Fit: {role_fit} | {operator} | {seniority}

{f'🚩 Стоп-факторы: {stop_flags}' if stop_flags != 'NONE' else ''}

CV: {'подаём шаблоном ✅' if cv_ready == 'YES' else f'нужна доработка ⚠️'}
{cv_note if cv_note else ''}

{summary}
    """
```

---

## Модуль: sheets.py — Google Sheets

### Аутентификация

Использовать Service Account (JSON файл). Дать доступ к таблице через `Share` на email сервис-аккаунта.

```python
import gspread
from google.oauth2.service_account import Credentials

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_sheet():
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_JSON, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(GOOGLE_SHEET_ID).worksheet('Pipeline')
```

### check_duplicate(company, role) → bool | dict

- Получить все строки
- Искать совпадение по `Company` + `Role` (case-insensitive, strip)
- Если найдено → вернуть `{'found': True, 'max_submission': N}`
- Если нет → вернуть `{'found': False}`

### add_row(data: dict)

Маппинг полей из `joe.evaluate()` в колонки таблицы:

```python
ROW_TEMPLATE = {
    'Company': data['company'],
    'Role': data['role'],
    'Region': data['region'],
    'Seniority': data['seniority'],
    'Operator vs Contractor': data['operator'],
    'Status': 'New',
    'Submission #': data.get('submission_num', 1),
    'Reapply Reason': data.get('reapply_reason', ''),
    'Applied Date': '',
    'Follow-up 1': '',
    'Follow-up 2': '',
    'Response Date': '',
    'Days to First Response': '',
    'Source': data.get('source_url', ''),
    'Channel': data['channel'],
    'Role Fit': data['role_fit'],
    'Stop Flags': '' if data['stop_flags'] == 'NONE' else data['stop_flags'],
    'Contact': '',
    'CV': '',
    'CL': '',
    'Comment': data.get('summary', ''),
}
# Записать в конец листа в строгом порядке колонок
```

---

## Модуль: parser.py — Парсинг ссылок

```python
import httpx
from bs4 import BeautifulSoup

def parse_url(url: str) -> str | None:
    # GET запрос с User-Agent браузера
    # Извлечь основной текст (body text, убрать навигацию/footer)
    # Если текст < 200 символов → вернуть None
    # Вернуть очищенный текст
    
    # Примечание: LinkedIn вернёт login page — это нормально.
    # Проверку на LinkedIn делать ДО вызова parse_url в bot.py
```

---

## Модуль: scheduler.py — Напоминалки в Telegram

### Логика (запуск каждый день в 08:00 по Dubai time, UTC+4)

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def daily_followup_check(bot, chat_id, sheet):
    today = datetime.date.today()
    rows = sheet.get_all_records()
    
    reminders = []
    for row in rows:
        for col in ['Follow-up 1', 'Follow-up 2']:
            date_str = row.get(col, '')
            if date_str:
                try:
                    d = datetime.datetime.strptime(date_str, '%d.%m.%y').date()
                    if d == today:
                        reminders.append(f"• {row['Company']} — {row['Role']} [{col}]")
                except:
                    pass
    
    if reminders:
        msg = "📅 Follow-up сегодня:\n\n" + "\n".join(reminders)
    else:
        msg = "✅ Follow-up на сегодня нет"
    
    await bot.send_message(chat_id=chat_id, text=msg)
```

---

## requirements.txt

```
python-telegram-bot==20.7
anthropic>=0.25.0
gspread>=6.0.0
google-auth>=2.0.0
httpx>=0.27.0
beautifulsoup4>=4.12.0
apscheduler>=3.10.0
python-dotenv>=1.0.0
```

---

## Что НЕ входит в MVP (не реализовывать сейчас)

- Генерация CL/CV через бота
- Сканер чата для подборок Perplexity (v2)
- Парсинг LinkedIn (отдельная задача)
- Аналитика откликов (v2)
- Web UI

---

## Порядок сборки (для Cursor agent)

1. Создать структуру проекта и `requirements.txt`
2. Реализовать `config.py` и `.env.example`
3. Реализовать `joe.py` — оценка через Claude API
4. Реализовать `sheets.py` — чтение/запись/дубли
5. Реализовать `parser.py` — парсинг URL
6. Реализовать `scheduler.py` — ежедневный триггер
7. Реализовать `bot.py` — handlers и inline кнопки
8. Собрать `main.py` — запуск всего
9. Протестировать локально с тестовым JD текстом
10. Подготовить инструкцию по деплою (Railway / Render)
