# Frontend (Joe Application Assistant)

React + Vite frontend for the Joe pipeline UI.

## Run locally

```bash
npm install
npm run dev
```

Default dev URL: `http://localhost:5173`

## Build

```bash
npm run build
npm run preview
```

## Environment

The frontend sends requests to backend API and uses Basic Auth credentials from browser session.

Key variable:
- `VITE_API_BASE_URL` (example: `http://localhost:8000`)

## Main screens

- Pipeline
- Vacancy Card
- CV Tailoring
- Cover Letter
- Dashboard

## Notes

- Frontend is designed to work with backend routes under `/api/*`.
- Sorting/filtering/status flows should always be validated against real backend data after UI changes.
- Pipeline table: no `NEW` pill near row id; rows with status `New` use pale-blue row highlight.
- JobCard touchpoints: date is displayed as `dd-mm-yy`; channel/source selector and touchpoint date-time editing are intentionally disabled in card UI.
