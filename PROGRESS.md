# Progress Log

## Project: Joe v2 MVP

---

## 2026-02-24
- feat: Project structure created — backend (FastAPI) + frontend (React/Vite/Tailwind)
- feat: Data model — Job with statuses, flags, fit levels (Pydantic)
- feat: 3 AI modules — CV tailor, Letter generator, Scoring evaluator (plug-in architecture)
- feat: Google Sheets service — read/write/cache pipeline data
- feat: Claude API service — centralized AI calls
- feat: Canon service — loads CLIENT_SPACE files as context
- feat: API routes — /jobs, /cv/tailor, /letter/generate, /scoring/evaluate, /pipeline/stats
- feat: 5 frontend pages — Pipeline, JobCard, CVScreen, LetterScreen, Dashboard
- feat: API client layer with TypeScript types
- fix: Aligned data model with real Google Sheets (21 columns)
- feat: Aligned backend with existing Telegram bot
- **smoke: All 6 backend tests passed** (health, sheets auth, worksheet, duplicates, URL parsing, add_to_tracker)
- **smoke: Claude API verified** (single call test)

## 2026-02-26
- fix: Frontend now requires Basic Auth login before loading app
- fix: Removed internal API key usage from frontend client
- docs: Expanded MVP product description (architecture, services, bot, repo)
- feat: Pipeline screen — AddJobBar (URL/text input → evaluate/add), LetterPopup (click CL → modal), polished table with 83 real jobs
- feat: JobCard screen — scoring, inline status editor, all data sections, actions
- feat: CVScreen — tailor CV with canon check, copy changes/full CV, re-tailor
- feat: LetterScreen — generate with notes, copy body/subject, word count, done/regenerate
- feat: Dashboard — summary cards, pipeline funnel bar chart, recent activity table
- fix: CORS — added ports 5174, 5175 to allow_origins
- docs: Developer permissions added to CLAUDE.md

## 2026-02-25
- feat: PDF export — WeasyPrint service renders CV (markdown→PDF) and cover letter (text→PDF)
- feat: Backend endpoints POST /cv/pdf and /letter/pdf return styled PDF files
- feat: Frontend "Download PDF" buttons on CV and Letter screens
- fix: Corrections Pack #1 — 36 items across backend and frontend:
  - feat: Unified JobStatus enum (8 canonical statuses), GET /jobs/statuses endpoint
  - feat: Jina Reader API for JD parsing (with BS4 fallback)
  - feat: Duplicate detection — URL exact match + fuzzy company/role/region
  - feat: needs_followup computed field (Applied + 4 days without response)
  - fix: Scoring flags — removed invalid geo/contractor, only 5 valid flags remain
  - feat: Logging in CV/Letter/Scoring modules
  - feat: Better error messages (specific errors, not "check backend")
  - feat: Event log system — Events worksheet in Google Sheets
  - feat: Auto-log status changes, manual touchpoints via POST /jobs/{id}/events
  - feat: Pipeline — Days column, DTR column, status filter, sortable columns
  - feat: Pipeline — duplicate marker, follow-up icon, fit color dots
  - feat: JobCard — source as domain link, timeline at top, status dropdown with chevron
  - feat: JobCard — touchpoint history with add form
  - feat: JobCard — simplified buttons (primary left, no Back)
  - feat: CVScreen — removed Step label, added Joe recommendation, re-tailor with input
  - feat: CVScreen — Use Canon / Tailor CV choice buttons
  - feat: LetterScreen — navigation back to card (not CV)
  - style: cursor-pointer on all interactive elements

---

## TODO
- [x] Telegram bot integration (existing bot → same Google Sheets)
- [x] Google Sheets integration testing — 83 jobs from real sheet
- [x] Claude API integration testing — OK
- [x] Pipeline screen — table + add job + letter popup
- [x] JobCard screen — scoring, status edit, sections
- [x] CV screen — tailor with canon check
- [x] Letter screen — generate, copy, regenerate
- [x] Dashboard — funnel, stats, recent activity
- [x] PDF export (WeasyPrint)
- [x] Corrections Pack #1
- [ ] Deploy to Railway

## Future (from Corrections Pack #1)
- [ ] Visual flow (stepper/progress bar)
- [ ] CV version history (save each tailoring)
- [ ] Russian resume (ready-made, not tailoring)
- [ ] Dashboard improvements
- [ ] Reapply flow (new application for same job)
- [ ] Telegram bot webhook integration
