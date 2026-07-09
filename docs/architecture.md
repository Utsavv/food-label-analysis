# LabelWatch India — Architecture

## Guiding principle

> Deterministic code owns scraping, storage, scheduling, diffing, validation and API
> responses. ADK agents own orchestration for interactive use, ambiguous interpretation,
> ingredient explanation, label-change summarization and user-facing analysis.

LLMs never sit in the control loop of scheduled production checks, never compute diffs,
and never decide significance scores. They rephrase and contextualize facts that
deterministic code has already established — and their JSON output is schema-validated
before use, falling back to the deterministic generators when invalid.

## Data flow (one label check)

```
ProductSource (URL, source_type)
        │
        ▼
SourceAdapter.fetch()            deterministic  (robots.txt, rate limit, UA; httpx →
        │                                        Playwright fallback; mock:// fixtures)
        ▼
ArtifactStore.save_snapshot()    deterministic  (HTML + text evidence, label images)
        │
        ▼ (thin page text + images?)
OCRProvider.extract_text()       deterministic  (google_vision | tesseract | mock)
        │
        ▼
parse_label_text()               deterministic  (regex parsing → StructuredLabel)
        │
        ├── overall_confidence < 0.5 ──► LabelExtractionAgent (Gemini, schema-validated,
        │                                 discarded if invalid; provenance recorded)
        ▼
compute_version_hash()           deterministic  (content signature, ignores noise)
        │
        ├── hash == previous ──► ScrapeRun.status = "no_change", stop
        ▼
persist_label_version()          deterministic  (label_versions + normalized child rows)
        │
        ▼
diff_labels() + score_diff()     deterministic  (typed diff items, 0-100 significance,
        │                                        category-aware thresholds)
        ▼
ChangeAnalysisAgent              agent          (plain-English report; facts locked to diff)
HealthContextAgent               agent          (audience-specific context; disclaimer enforced)
        │
        ▼
ai_analyses                      stored with model_name, prompt_version, confidence,
                                 timestamp, comparison_id / label_version_id
```

## The agents (Google ADK)

| Agent | Role | Tools |
|---|---|---|
| `LabelMonitorAgent` | Conversational orchestrator of the whole check workflow (`adk web`). Production scheduling uses the deterministic pipeline calling the *same tool functions*. | fetch_manufacturer_page, run_ocr, parse_label_text, save_label_version, create_comparison, compare_label_versions, generate_change_analysis, explain_ingredient |
| `LabelExtractionAgent` | Parse messy OCR/web text into strict `StructuredLabel` JSON. Never invents values; output is Pydantic-validated. | — (pure reasoning) |
| `IngredientExplainerAgent` | Plain-English ingredient explanations with realistic consumer context. | — |
| `ChangeAnalysisAgent` | Reads the deterministic scored diff, writes "what changed / why it matters / who should care". Significance scores are overwritten from the deterministic values after the call. | — |
| `HealthContextAgent` | Audience-specific health context. The non-medical disclaimer is enforced in code, not trusted to the model. | — |

`app/agents/root_agent.py` wires them into a root coordinator for `adk web`.

Mock mode (`LLM_PROVIDER=mock`, the default) replaces each agent's LLM call with a
deterministic generator (`services/analysis/`) that produces the same JSON structure, so
the full product works offline and tests are stable. Provenance is honest: mock outputs
are stored with `model_name="mock-rule-based"`.

## Extensibility decisions

- **New food category** → it's just a new `category` string on `products`, plus optional
  entries in `CATEGORY_OVERRIDES` (scoring thresholds). No schema change.
- **New source type** (retailer page, uploaded image, public database, manual entry) →
  implement a `SourceAdapter` and `register_adapter()`. The pipeline is adapter-agnostic;
  `mock` and `manual` adapters already demonstrate the pattern.
- **New OCR engine** → implement `OCRProvider`.
- **Scheduler migration** → `check_all_active_products()` is a self-contained entry point
  for Cloud Scheduler / Cloud Run Jobs / Pub/Sub consumers.
- **Artifact storage** → `ArtifactStore` isolates filesystem paths; a GCS implementation
  swaps in behind the same two methods.

## Database schema

Normalized tables (`products`, `product_sources`, `scrape_runs`, `label_versions`,
`nutrition_items`, `ingredients`, `allergens`, `certifications`, `label_claims`,
`label_comparisons`, `ai_analyses`) with `JSONB` (PostgreSQL) / `JSON` (SQLite) for the
flexible payloads `structured_json`, `diff_json`, `analysis_json`. Normalized child rows
exist for search/filtering; the JSON payloads remain the source of truth for
diffing/rendering. Alembic owns migrations; `init_db()` covers quick-start/tests.

## Significance scoring model

Each diff item gets a 0–100 score from `BASE_SCORES` (per diff type) and
`NUTRIENT_THRESHOLDS` (percent-change bands per nutrient, direction-aware — a protein
*drop* matters more than a rise; sodium *rise* matters more than a drop). Category
overrides tighten thresholds where it matters (protein in protein powders). Overall score
= max item score plus a small co-occurrence bonus, capped at 100. Levels: ≥80 very_high,
≥60 high, ≥35 medium, ≥10 low, else minimal.

## Failure visibility

Every check writes a `scrape_runs` row (`pending/running/success/no_change/failed`,
`error_message`, timestamps). Failed runs surface on the dashboard. Robots.txt blocks and
Amazon URLs fail loudly rather than being silently skipped. A failing product never blocks
the weekly sweep (per-product transactions).
