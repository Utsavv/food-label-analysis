# 🏷️ LabelWatch India

Agentic AI web application that monitors packaged-food labels in India — starting with
**protein powders** and **protein bars** — tracks how labels change over time, and explains
those changes in plain English for consumers and fitness users.

> ⚠️ **Disclaimer:** All analysis produced by this project is informational and **not medical
> advice**. Always check the actual product label and consult a qualified professional for
> medical or allergy-related decisions.

## What it does

1. **Tracks labels over time** — weekly scheduled checks per product plus a manual
   "Run check now" button. Every check stores the original evidence (page snapshot,
   extracted text, label images).
2. **Detects meaningful changes** — a deterministic diff engine compares label versions:
   nutrition amounts, ingredients (including order), allergens, certifications, claims,
   serving size, warnings, FSSAI license, veg/non-veg mark.
3. **Scores significance (0–100)** — rule-based, with configurable per-nutrient and
   per-category thresholds (allergen added ≈ 95, protein drop in a protein powder ≈ 85,
   rounding noise ≈ 5).
4. **Explains changes in plain English** — Google ADK agents (Gemini) produce
   "what changed / why it matters / who should care" reports and audience-specific health
   context (fitness users, sugar watchers, hypertension, allergies, vegetarians/vegans,
   sweetener-sensitive). In demo mode a deterministic rule engine produces the same
   structure with zero credentials.
5. **India-first labeling concepts** — FSSAI license numbers, vegetarian/non-vegetarian
   marks, INS additive numbers, Indian claim vocabulary ("high protein", "no added sugar",
   …). The schema is category-agnostic: new food categories are just new `category` strings
   plus optional scoring thresholds.

## Architecture in one paragraph

**Deterministic code owns** scraping (robots.txt-respecting, rate-limited), OCR, storage,
label parsing, version hashing, diffing, significance scoring, scheduling and the API.
**Google ADK agents own** reasoning: `LabelMonitorAgent` (orchestration for interactive
use), `LabelExtractionAgent` (messy-text extraction assist, schema-validated),
`IngredientExplainerAgent`, `ChangeAnalysisAgent`, and `HealthContextAgent`. Agents call
the same deterministic functions that the pipeline uses, exposed as ADK tools. Every AI
output is stored with model name, prompt version, timestamp, confidence and the source
label version. See [docs/architecture.md](docs/architecture.md) for details.

## Quick start (Docker, recommended)

```bash
cp .env.example .env      # defaults are fine for demo mode
docker compose up --build
```

- Frontend: http://localhost:3000
- API + docs: http://localhost:8000/docs
- PostgreSQL migrations and demo seed data run automatically.

## Quick start (local, no Docker)

Backend (Python 3.11+, SQLite by default):

```bash
cd backend
pip install -e '.[dev]'
alembic upgrade head          # or skip: tables auto-create on startup
python -m seed.seed_demo      # demo products with label history
uvicorn app.main:app --reload # http://localhost:8000/docs
```

Frontend (Node 20+):

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173 (proxies /api to :8000)
```

## Demo walkthrough

The seed creates two products whose sources are local fixtures (`mock://…`), so the entire
flow works offline:

1. **MaxFit Whey Gold (protein powder)** — v1→v2: sodium 120→190 mg, protein 24→22 g,
   sucralose + maltodextrin added, "no artificial sweetener" claim removed.
   Significance ≈ 96/100.
2. **NutriCrunch Peanut Protein Bar** — v1→v2: soy allergen added, "may contain tree
   nuts/cashew" added, "no added sugar" claim removed, added sugar 0→4 g.
   Significance = 100/100.

Open a product → view current label, version history, click any ingredient for a
plain-English explanation → open the comparison for the diff tables and AI analysis.
"Run check now" re-fetches the source (reports *no change* since the fixture is stable —
point the source at another fixture to see a new version created).

## Running tests

```bash
cd backend && python -m pytest       # 51 tests: parsing, diff, scoring, API, agents
cd frontend && npm test              # vitest component tests
```

## What is mocked / what needs credentials

| Piece | Demo mode (default) | Production mode |
|---|---|---|
| LLM agents | Deterministic rule-based generators (`model_name: mock-rule-based`) | `LLM_PROVIDER=google` + `GOOGLE_API_KEY` + `pip install '.[ai]'` → Gemini via Google ADK |
| OCR | Mock (reads sidecar `.txt` files) | `OCR_PROVIDER=google_vision` (GCP credentials) or `tesseract` |
| Scraping | `mock://` fixture adapter | `manufacturer` adapter does real fetches (httpx, optional Playwright via `pip install '.[playwright]'`) |
| Database | SQLite | PostgreSQL (`DATABASE_URL`), JSONB columns used automatically |
| Scheduler | Disabled locally | `ENABLE_SCHEDULER=true` → APScheduler weekly cron |

To try the real ADK agents interactively: `pip install '.[ai]'`, set `GOOGLE_API_KEY`,
then `adk web` from `backend/app` (the root agent lives in `app/agents/root_agent.py`).

## Scraping & legal notes

- The scraper checks `robots.txt`, rate-limits per host, sends a clear bot user-agent,
  and **never bypasses anti-bot systems** — blocked fetches are recorded as failed runs.
- Amazon scraping is explicitly not supported in the MVP.
- Source attribution (URL, timestamp, snapshot) is stored with every label version.
- **Respect website terms of service and applicable law** (including Indian IT law and
  the target site's jurisdiction) before scraping any source. Prefer manufacturer pages,
  public databases, or manual/uploaded labels where terms are unclear.
- AI analysis is informational, never medical advice; the disclaimer is enforced
  server-side on every health-context output and shown in the UI.

## API surface

`POST /products` · `GET /products` · `GET /products/{id}` · `POST /products/{id}/sources` ·
`POST /products/{id}/check-now` · `GET /products/{id}/label-versions` ·
`GET /products/{id}/comparisons` · `GET /comparisons/{id}` · `GET /label-versions/{id}` ·
`GET /ingredients/explain` · `GET /runs` · `GET /dashboard/stats` · `GET /health`

## Recommended next steps for Google Cloud production

1. **Cloud Run** for the API and frontend; **Cloud SQL (PostgreSQL)** with the existing
   Alembic migrations.
2. Replace the in-process APScheduler with **Cloud Scheduler → Pub/Sub → Cloud Run Job**
   invoking `app.services.scheduler.weekly_checker.check_all_active_products` (the
   function is already entry-point shaped).
3. Move `ArtifactStore` to **GCS** (the interface is a drop-in: save_snapshot/save_images).
4. **Vertex AI / Gemini** for agents (set `LLM_PROVIDER=google`), Google Cloud Vision for
   OCR, and Secret Manager for keys.
5. Add auth (Identity Platform), per-user product lists, and notification delivery
   (email/push on high-significance changes).
6. Observability: structured logs already include run status/errors; add Cloud Monitoring
   alerts on failed-run rate.
