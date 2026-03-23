# Local Snapshot — 2026-02-26

> Historical snapshot (point-in-time). Paths, deploy details, and risks reflect 2026-02-26 only.

This file is a local, human-readable checkpoint of what was done so the session can resume later.

## Repos and Branches
- Repo: `https://github.com/Ksen-Kas/joe_services`
- Active web/MVP branch: `mvp-service`
- Legacy Telegram bot on: `main`
- Checkpoint branch created earlier: `checkpoint-2026-02-26-telegram-bot`

## Deploy State (Railway)
- Project: `joe-bot-apply`
- Env: `production`
- Backend domain: `https://backend-production-4088.up.railway.app`
- Frontend domain: `https://frontend-production-6628.up.railway.app`
- GitHub-based deploys enabled for both services (branch `mvp-service`)
- Frontend start fixed to bind `$PORT`:
  - `NIXPACKS_START_CMD=npx --yes serve -s dist --listen $PORT`
- Backend PDF deps attempt (Railpack):
  - `RAILPACK_APT_PACKAGES=libglib2.0-0 libgobject-2.0-0 libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libffi8 libharfbuzz0b libfribidi0 libjpeg62-turbo libpng16-16 fonts-dejavu-core`

## Security/Access
- Frontend requires login (Basic Auth) before showing app.
- `VITE_INTERNAL_API_KEY` removed from frontend.
- Backend internal endpoints now accept **Basic Auth** in addition to `X-App-Key`.
- Rotated in Railway backend:
  - `API_ACCESS_PASSWORD`
  - `INTERNAL_API_KEY`
  (values not stored here; use Railway Variables + password manager)

## Key Product Changes (MVP)
- Dark theme redesign (Phantom-like):
  - `frontend/src/index.css` `@theme` tokens
  - App/Pipeline/JobCard/CV/Letter/Dashboard restyled
- Duplicate icon replaced with minimal overlap glyph; moved to Company column
- JobCard scoring: JD input box + error display; uses source URL or pasted JD
- CV/Letter: copy & PDF actions now show user feedback

## Scoring Rules Update
- `visa_required` and `citizenship` flags are now kept **only if** JD contains explicit wording.
- Implemented in `backend/modules/scoring/evaluate.py`:
  - `_validate_stop_flags()` filters flags unless explicit markers exist.

## Statuses Update
- Added statuses: `Screening`, `Screening Req`
  - Backend: `backend/app/models/job.py`
  - Frontend: `frontend/src/constants/statuses.ts`
  - Purple badge styling in `frontend/src/pages/Pipeline.tsx`

## Telegram Bot (Legacy)
- Deployed from `main` in `joe_services`.
- Changed behavior: no scoring, no Claude tokens.
- On URL → adds row immediately.
- LinkedIn URL → adds row with comment “insert JD manually”.
- Long JD text (>200 chars) → adds row with Unknown company/role + comment.
- Current `mvp-service` backend scheduler sends daily Telegram reminders by product rules:
  - Stale New (New + 3 days)
  - Follow-up 1 (Applied + 4 days)
  - Follow-up 2 (FU1 + 7 days)
  - No Response (Applied + 30 days)
  - Auto status updates
  - "Напоминаний на сегодня нет" if no items are due

## Docs Updated
- `docs/JOE_V2_MVP_PRODUCT_DESCRIPTION.md`:
  - added architecture summary, services/modules, Telegram bot behavior, git repo link.

## Smoke/Checks Done
- Backend health: OK
- Scoring with Basic Auth: OK (no forced logout)
- Stop-flags rule validated with two test JDs.
- Any smoke-created row was deleted afterward.
- PDF endpoints: still failing on prod due to WeasyPrint libs; fallback added (see below).

## Known Gaps / Notes
- Follow-up reminders are **not** derived from touchpoints.
- Telegram push is sent from web backend scheduler (`backend/app/services/reminder.py`).
- PDF export: WeasyPrint missing system libs in Railway. Fallback PDF added:
  - `backend/app/services/pdf.py` uses `fpdf2` if WeasyPrint fails.
  - Unicode and long-token handling added, but PDF still failing on prod (investigation ongoing).
