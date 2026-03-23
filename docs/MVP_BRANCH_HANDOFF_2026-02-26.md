# MVP Branch Handoff (for next chat)

> Historical handoff document from 2026-02-26. Keep as archive; validate all operational details against current docs before executing.

## 1) Context Snapshot

- Repository: `https://github.com/Ksen-Kas/joe_services`
- Working branch for MVP: `mvp-service`
- Branch commit: `570efd7` (`feat: introduce MVP service stack in mono-repo`)
- PR to `main`: `https://github.com/Ksen-Kas/joe_services/pull/1`
- Important constraint from product owner: keep everything in the same repository (`joe_services`), no separate repo.

## 2) What Was Done

- Introduced a new Joe MVP service stack in this repo:
  - FastAPI backend in `backend/`
  - React + Vite frontend in `frontend/`
  - Module structure for CV/Letter/Scoring in `backend/modules/`
- Preserved existing `main` branch state (legacy bot remains untouched there).
- Added production-hardening and deploy-related changes:
  - Basic auth middleware (backend)
  - Internal API key checks for sensitive endpoints
  - noindex controls (`X-Robots-Tag`, `<meta robots>`, `robots.txt`)
  - CORS via env (`ALLOWED_ORIGINS`)
  - SSRF guardrails in URL parser (block local/private targets)
  - Canon fallback via env variables (`CANONICAL_RESUME_CONTENT`, etc.)
  - Lazy import for WeasyPrint to prevent API startup crash when system libs are missing
- Added contact parsing flow:
  - `backend/app/services/contact_parser.py`
  - `contact` passed from frontend AddJobBar to scoring and then to Google Sheets contact column.

## 3) Deploy State (Railway)

- Railway project: `joe-bot-apply`
- Environment: `production`
- Services:
  - `backend` (status: SUCCESS)
  - `frontend` (status: SUCCESS)
- Domains:
  - Backend: `https://backend-production-4088.up.railway.app`
  - Frontend: `https://frontend-production-6628.up.railway.app`

## 4) Security Model Currently Implemented

- Backend:
  - Basic auth required for requests (401 without auth)
  - Internal API key accepted (`X-App-Key`) and used for app-to-app access
  - CORS restricted by `ALLOWED_ORIGINS`
  - Security/noindex headers are set in middleware
  - OpenAPI/docs disabled in production (`APP_ENV=production`)
- Frontend:
  - Public static app URL
  - Sends `X-App-Key` from env (`VITE_INTERNAL_API_KEY`) in API client
  - Includes noindex meta and `robots.txt`

## 5) Known Risks / Caveats

- Frontend is publicly reachable. While backend is protected, SPA exposure and static key-in-client model is not ideal for strict private access.
- Secrets were shared in chat during setup; key rotation is strongly recommended.
- WeasyPrint PDF runtime deps are not installed at system level in Railway image; startup is stabilized via lazy import, but PDF endpoints may still fail if libraries are missing.
- Branch histories differ heavily between `origin/main` and MVP branch content; this is expected in PR #1.

## 6) Important Files Added/Changed (MVP)

- Backend core:
  - `backend/app/main.py`
  - `backend/app/config.py`
  - `backend/app/security.py`
  - `backend/app/routers/{jobs.py,cv.py,letter.py,scoring.py,pipeline.py}`
  - `backend/app/services/{sheets.py,parser.py,canon.py,pdf.py,claude.py,contact_parser.py}`
  - `backend/app/models/job.py`
  - `backend/requirements.txt`
- Modules:
  - `backend/modules/cv/*`
  - `backend/modules/letter/*`
  - `backend/modules/scoring/*`
- Frontend:
  - `frontend/src/pages/*`
  - `frontend/src/api/{client.ts,jobs.ts}`
  - `frontend/src/constants/statuses.ts`
  - `frontend/index.html`
  - `frontend/public/robots.txt`
  - `frontend/.env.example`
- Docs/support:
  - `docs/JOE_V2_MVP_PRODUCT_DESCRIPTION.md`
  - `smoke_backend.md`

## 7) Verified Behaviors

- Frontend build success (`npm run build`)
- Backend health returns 200 with auth
- Backend returns 401 without auth
- Production CV tailoring returns `CANON CHECK: OK` after canon fallback env setup

## 8) Current Git State (local)

- Current branch: `mvp-service`
- Upstream: `origin/mvp-service`
- Clean branch relative to upstream, except local untracked helper files:
  - `Untitled`
  - `sh-thd-1772180735`

## 9) Recommended Immediate Next Steps (for next chat)

1. Decide merge strategy for PR #1 into `main` (large structural replacement).
2. Move Railway deployment source to GitHub branch-based deploy (`mvp-service` first, then `main` post-merge).
3. Rotate sensitive secrets:
   - `API_ACCESS_PASSWORD`
   - `INTERNAL_API_KEY`
   - `ANTHROPIC_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - Google service credentials if needed by policy
4. Tighten private access further if required (e.g., edge/basic auth for frontend domain, not only backend API guards).
5. Decide strategy for PDF endpoints:
   - install system libs in runtime image OR
   - disable/hide PDF features in production until libs are available.
6. Run end-to-end smoke from UI after merge/deploy source switch.

## 10) Handy Commands

```bash
# Branch/PR context
git checkout mvp-service
git log --oneline origin/main..HEAD

# Railway quick status
railway status
railway service status --all --json

# Domains
railway domain --service backend --json
railway domain --service frontend --json

# Push branch updates
git push origin mvp-service
```
