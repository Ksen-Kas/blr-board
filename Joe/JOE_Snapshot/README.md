# Core Hub Repository (working)

This repo is a **portable memory + bootstrap kit** for Ksenia’s system (Core + agents), with a focus on **job search projects** (starting with Andrey).

## What lives here
- **Canonical facts** (e.g., Andrey CV canon) — the source of truth.
- **Core/agent kernels** — reusable prompts / operating rules.
- **Snapshots** — “known-good” states we can restore.
- **Pipelines** — how we actually run the work, end-to-end.

## How we use it in ChatGPT Projects
1) Put canonical files into the Project “Files”.
2) Start (or restart) a working thread.
3) Paste the relevant initializer (from `/kernels/`).
4) When we change a canon, we update the file here **and** in the Project Files.

## Key rule
If a thread drifts or starts inventing: we run **FACT_CHECK** against canonical files (see `/kernels/FACT_CHECK.md`).
