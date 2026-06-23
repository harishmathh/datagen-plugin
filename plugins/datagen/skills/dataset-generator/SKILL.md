---
name: Dataset-Generator
description: Generate synthetic yet realistic datasets from a business context, objective, and comments. End-to-end workflow — (1) runs Dataset-Research to ground the domain in real-world data and produce a reviewed spec, (2) compiles a human-readable YAML recipe (the generation contract — distributions, relationships, correlations, conditional logic, constraints, multi-table foreign keys, and LLM/Faker text columns), presents it for review, then (3) runs a seeded Python engine to build the linked datasets efficiently, filling text columns via the Anthropic API in batches, and produces a validation report. Use whenever the user wants to create a synthetic dataset, fake/mock data, test data, or a sample dataset that should look realistic for a given business — e.g. "generate customer/spending/engagement datasets for this retail company", "make a realistic synthetic dataset for X". Asks for confirmation at the spec and recipe checkpoints before generating.
---

# Dataset-Generator

Produce realistic synthetic datasets from a plain-English business brief. The
pipeline is **research → recipe → generate**, with a human review gate at each
of the first two stages. It wraps the **Dataset-Research** skill as its first
step.

The company can be fictional; the data should look like it came from a real
business of that type. Realism comes from grounding (research), structure
(distributions + relationships + constraints), and integrity (linked tables
sharing keys).

## Inputs
- **Business context**, **Objective**, **Additional comments** (which datasets,
  sizes, anything special). Ask for any that are missing.

## Output location
One run directory `outputs/<slug>/` (`<business-name>-<YYYYMMDD>`), containing:
`spec.md`, `spec.html`, `recipe.yaml`, `recipe.html`, the generated `*.csv`
files, `generation_report.json`, and `report.html`.

`${CLAUDE_PLUGIN_ROOT}` is the plugin root; the engine lives at
`${CLAUDE_PLUGIN_ROOT}/engine/`.

## Stage 0 — Setup (once)
Ensure deps are available (the engine degrades gracefully if optional ones are
missing):
```bash
python -m pip install -r "${CLAUDE_PLUGIN_ROOT}/requirements.txt"
```
For LLM text columns, `ANTHROPIC_API_KEY` must be set; otherwise text columns
fall back to clearly-marked placeholders and you should tell the user.

## Stage 1 — Research (delegate to Dataset-Research)
Invoke the **Dataset-Research** skill with the same inputs. It produces and
gets the user to confirm `outputs/<slug>/spec.md`. **Do not proceed past the
spec until the user has validated it.** The confirmed spec — especially its
Section 6 dataset blueprint and Sections 4–5 (distributions, relationships,
constraints) — is the source of truth for the recipe.

## Stage 2 — Compile the recipe
Translate the confirmed spec into `outputs/<slug>/recipe.yaml`. This is the
*generation contract*: it must contain everything needed to build the data, so
generation is deterministic and reviewable.

Use `recipe_template.yaml` (this skill's directory) as the feature reference
and `${CLAUDE_PLUGIN_ROOT}/engine/recipe.schema.json` as the authority. Encode:

- **Shared entities** for every cross-table key (e.g. a `customers` pool keyed
  on `customer_id`) so all tables join cleanly — *full referential integrity*.
- **Per-dataset grain, key, and size.** Size: scale sensibly from the real
  population in the spec (e.g. a ~10k sample of a 1.4M base), capped reasonably.
  Use `rows: "per:<entity>*N"` for child/event tables.
- **Columns with grounded distributions** (the params from spec Section 4):
  numeric (normal/lognormal/poisson/beta/gamma/…), categorical (weighted),
  datetime (with seasonality), boolean.
- **Relationships:** `correlate_with` for numeric correlations; `conditional`
  distributions keyed on another column; `inherit` to pull a column from a
  sibling table (e.g. `segment` from `customers`) so dependent tables condition
  on it; `derived` columns for computed fields.
- **Constraints** (spec Section 5) with a `repair` strategy each.
- **Outliers** where the spec calls for them (whales, dormant accounts, …).
- **Text columns:** `faker` for structured text (names, cities, emails);
  `type: text` with an `llm` block for genuine free text — always set
  `cardinality` + `conditioned_on` to control cost.
- A fixed `meta.seed` for reproducibility.

Validate the recipe before showing it:
```bash
python "${CLAUDE_PLUGIN_ROOT}/engine/validate_recipe.py" "outputs/<slug>/recipe.yaml"
```

## Stage 3 — Present the recipe for review (confirmation gate)
Render and publish the recipe artifact:
```bash
python "${CLAUDE_PLUGIN_ROOT}/engine/render.py" recipe \
  "outputs/<slug>/recipe.yaml" "outputs/<slug>/recipe.html"
```
Publish `recipe.html` as an **Artifact** (tables of every column with its
distribution, correlation/conditional badges, constraints, entity diagram). In
chat, summarize: tables + row counts, the key relationships encoded, anything
using the LLM, and the seed. **Ask the user to confirm or amend before
generating.** Note expected LLM cost/row count if text columns are present.

## Stage 4 — Generate
Run the engine. It builds each table deterministically, links via the shared
keys, enforces constraints (resample/clip/drop), and fills text columns in
batched parallel API calls (cached on disk).
```bash
python "${CLAUDE_PLUGIN_ROOT}/engine/generate.py" \
  --recipe "outputs/<slug>/recipe.yaml" \
  --out    "outputs/<slug>" \
  [--rows-scale 0.1]   # quick preview at 10% size, optional
  [--offline]          # skip LLM, use placeholders
  [--only customers,spendings]   # subset of tables
```
For very large runs or independent tables, you may also fan out generation per
table with the Agent tool (each agent runs `generate.py --only <table>`), but
the single-process engine already parallelizes LLM calls and handles
inheritance ordering, so prefer one call unless tables are independent and huge.

**Recommended flow:** first run with `--rows-scale 0.1` (or `--offline`) as a
fast preview, show the validation report, then do the full run on confirmation.

## Stage 5 — Validate & present results
Render and publish the validation report:
```bash
python "${CLAUDE_PLUGIN_ROOT}/engine/render.py" report \
  "outputs/<slug>/generation_report.json" "outputs/<slug>/report.html"
```
Publish `report.html` as an **Artifact**. It shows per-column summary stats,
distribution-fidelity checks vs the recipe, categorical drift, and foreign-key
integrity. In chat: confirm row counts, FK integrity (should be clean),
constraint satisfaction, and point to the CSV files. Call out any warnings.

## Confirmation gates (do not skip)
1. After the **spec** — user validates the grounded research.
2. After the **recipe** — user validates the generation contract.
Generation only runs after gate 2. Mention LLM usage/cost before incurring it.

## Reference files
- `recipe_template.yaml` — annotated reference for every recipe feature.
- `${CLAUDE_PLUGIN_ROOT}/engine/recipe.schema.json` — recipe JSON schema.
- `${CLAUDE_PLUGIN_ROOT}/engine/generate.py` — the generation engine.
- `${CLAUDE_PLUGIN_ROOT}/engine/render.py` — `spec` / `recipe` / `report` renderers.
- `${CLAUDE_PLUGIN_ROOT}/engine/validate_recipe.py` — standalone recipe validator.
