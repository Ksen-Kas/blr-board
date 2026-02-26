# Lessons Learned

Insights, gotchas, and decisions made during development.

---

## Architecture

- Job identification: sheet row_num (not UUID) — bot writes rows directly
- No separate jd_text column — JD summary stored in Comment column
- Bot and web share the same Google Sheet (worksheet "Pipeline")
- Scoring uses the SAME system prompt and output format as the bot (joe_system_prompt.txt)
- The web backend loads the bot's prompt file directly from the bot directory

---

## Google Sheets API

- 21 columns: Company, Role, Region, Seniority, Operator vs Contractor, Status, Submission #, Reapply Reason, Applied Date, Follow-up 1, Follow-up 2, Response Date, Days to First Response, Source, Channel, Role Fit, Stop Flags, Contact, CV, CL, Comment
- Sheet ID: 1hteRUUcM3Q1w-Pf2ZnY4Igl239Od3b4DJTTMNp2WT_M
- Worksheet name: "Pipeline" (not sheet1!)
- Auth: GOOGLE_CREDENTIALS_JSON_CONTENT env var contains full service account JSON as string
- Auth method: `Credentials.from_service_account_info(json.loads(...))` — NOT from_service_account_file
- Status values in use: New, Screening, Screening req, Applied, HR Screen, Interview, Rejected
- Dates in DD.MM.YY format (European)
- Contact field: name + LinkedIn + phone in one cell
- Stop flags: "NONE" in bot output → empty string in sheet
- Bot's add_row maps "operator" field → "Operator vs Contractor" column

---

## Claude API

- Model: `claude-sonnet-4-6` (both bot and web backend)
- Bot uses structured text output (COMPANY:/ROLE:/STOP_FLAGS:), not JSON
- System prompt is ~22KB, loaded from joe_system_prompt.txt
- Output format appended to system prompt at call time
- max_tokens=1024 for scoring

---

## Telegram Bot (existing, Railway)

- Single-user design, in-memory state
- Handles: URL → parse → evaluate → add to tracker
- Handles: long text (>200 chars) → evaluate
- Duplicate check: case-insensitive company+role match
- Reapply flow: asks reason, increments Submission #
- Daily follow-up reminders via APScheduler (checks Follow-up 1/2 dates)

---

## React / Frontend

- Pipeline table sorts by status order
- Fit icons: 🟢 Clean / 🟡 Check / 🔴 Flags — same logic as bot

---

## Deployment

- Bot: Railway (Python)
- Web: TBD (Railway or Vercel)
- Both need the same env vars: ANTHROPIC_API_KEY, GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_JSON_CONTENT
