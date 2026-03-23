# Start Here

If you are a new agent/session, read in this order:

1. `README.md`
2. `PROGRESS.md`
3. `docs/PROJECT_BRIEF.md`
4. `docs/DEPLOY_SECURITY_BRIEF.md`
5. `docs/JOE_V2_MVP_PRODUCT_DESCRIPTION.md` (full product context)
6. `docs/LEGACY_ARCHIVE_INDEX.md`

## Active Workspaces
- Source repo (git): `/Users/sizovaka/Documents/AI_LAB/Projects/04_Joe-Application-Assistant`
- Runtime mirror (run from here): `/Users/sizovaka/Documents/AI_LAB/RUNTIME/joe-application-assistant`

## Continue From Last Points
- Open `PROGRESS.md` first and continue from the last date block + TODO section.
- Check latest commits on active branch:
  - `git -C /Users/sizovaka/Documents/AI_LAB/Projects/04_Joe-Application-Assistant log --oneline -n 10`
- If work touches reminders/Telegram, check:
  - `backend/app/services/reminder.py`
  - `docs/DEPLOY_SECURITY_BRIEF.md`

## Current Branch
`mvp-service`

## Rule of thumb
- `Projects/04_Joe-Application-Assistant` is source of truth for code history.
- `RUNTIME/joe-application-assistant` is operational mirror for runs/tests.
- Snapshot docs with dates (`*_2026-02-*.md`) are historical context, not current runtime truth.
