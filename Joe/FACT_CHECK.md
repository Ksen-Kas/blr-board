# FACT_CHECK · Canon Gate (Andrey)

Use this whenever we edit CV / letters / LinkedIn.

## Inputs
- Canonical CV file: `ANDREY_CV_CANON.md` (or whatever canon file name is used in the project)
- Draft text to validate

## Procedure
1) Extract every factual claim from the draft (roles, dates, locations, tools, achievements, money numbers, leadership scope).
2) Compare each claim to canonical CV:
   - If exact match → OK
   - If weaker/less specific → OK (safe compression)
   - If stronger/new detail → FLAG as **NON-CANON**
3) Output a compact report:
   - ✅ OK (canon-aligned)
   - ⚠️ NON-CANON (needs approval / remove)
   - 🟨 ASSUMPTION (needs source)
4) If any ⚠️ exists: propose the minimal rewrite that removes it.

## Output format (fixed)
- Drift score: Low / Medium / High
- ✅ OK:
- ⚠️ NON-CANON:
- 🟨 ASSUMPTION:
- Minimal safe rewrite:
