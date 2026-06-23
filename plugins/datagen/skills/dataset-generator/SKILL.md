---
name: Dataset-Generator
description: Generate synthetic yet realistic datasets from a business context, objective, and additional comments. End to end it (1) calls the Dataset-Research skill to ground the domain in real-world data and produce a reviewed spec, (2) compiles a human-readable YAML recipe (the generation contract: distributions, relationships, correlations, conditional logic, constraints, multi-table foreign keys, and LLM or Faker text columns), presents it for review, then (3) runs a seeded Python engine to build the linked datasets, fills text columns via the Anthropic API in batches, and produces a validation report. Use whenever the user wants to create a synthetic dataset, fake or mock data, test data, or a realistic sample dataset for a given business, for example "generate customer, spending, and engagement datasets for this retail company". Asks for confirmation at the spec and recipe checkpoints before generating.
---

# Dataset-Generator

Produce realistic synthetic datasets from a plain-English business brief. The
pipeline is **research, then recipe, then generate**, with a human review gate
at each of the first two stages. The research stage is not reimplemented here:
it is the **Dataset-Research** skill, which this skill calls and waits on.

The company can be made up; the data should look like it came from a real
business of that type. Realism comes from grounding (the research), structure
(distributions, relationships, constraints), and integrity (linked tables that
share keys).

## Required inputs (do not skip this)

Three inputs are mandatory:

1. **Business context** the company and what it does.
2. **Objective** what the dataset is for.
3. **Additional comments** which datasets to produce, sizes, and anything
   special.

If any of the three is missing or vague, **stop and ask the user.** Do not run
research, do not write a recipe, do not generate anything. Say plainly what is
missing and wait. Only with all three in hand do you start. This is a hard gate.

## Where the output goes

One run directory `outputs/<slug>/` (`<business-name>-<YYYYMMDD>`), holding:
`spec.md`, `research_report.html`, `recipe.yaml`, `recipe.html`, the generated
`*.csv` files, `generation_report.json`, and `report.html`.

`${CLAUDE_PLUGIN_ROOT}` is the plugin root; the engine lives at
`${CLAUDE_PLUGIN_ROOT}/engine/`.

## Stage 0, setup (once)

Make sure the deps are there (the engine degrades gracefully if the optional
ones are missing):

```bash
python -m pip install -r "${CLAUDE_PLUGIN_ROOT}/requirements.txt"
```

For LLM text columns, `ANTHROPIC_API_KEY` has to be set. Without it, text
columns fall back to clearly-marked placeholders, and you should tell the user
that up front.

## Stage 1, research (call Dataset-Research)

Invoke the **Dataset-Research** skill with the same three inputs. It does the
whole web-research phase, writes `outputs/<slug>/spec.md`, renders the HTML
report, and gets the user to confirm it. **Do not move past the spec until the
user has validated it.** The confirmed spec, above all its Section 6 dataset
blueprint and Sections 4 and 5 (distributions, relationships, constraints), is
the source of truth for the recipe.

Dataset-Research is the only place research happens. This skill does not redo
it; it consumes the grounded items the research produced.

## Stage 2, compile the recipe

Turn the confirmed spec into `outputs/<slug>/recipe.yaml`. This is the
generation contract: it has to hold everything needed to build the data, so
generation is deterministic and reviewable.

Use `recipe_template.yaml` (this skill's directory) as the feature reference and
`${CLAUDE_PLUGIN_ROOT}/engine/recipe.schema.json` as the authority. Encode:

- **Shared entities** for every cross-table key (for example a `customers` pool
  keyed on `customer_id`) so all tables join cleanly, with full referential
  integrity.
- **Per-dataset grain, key, and size.** Scale size sensibly from the real
  population in the spec (for example a ~10k sample of a 1.4M base), capped to
  something reasonable. Use `rows: "per:<entity>*N"` for child or event tables.
- **Columns with grounded distributions** (the params from spec Section 4):
  numeric (normal, lognormal, poisson, beta, gamma, and so on), categorical
  (weighted), datetime (with seasonality), boolean.
- **Relationships:** `correlate_with` for numeric correlations; `conditional`
  distributions keyed on another column; `inherit` to pull a column from a
  sibling table (for example `segment` from `customers`) so dependent tables can
  condition on it; `derived` columns for computed fields.
- **Constraints** (spec Section 5), each with a `repair` strategy.
- **Outliers** where the spec calls for them (whales, dormant accounts, and so
  on).
- **Text columns:** `faker` for structured text (names, cities, emails);
  `type: text` with an `llm` block for genuine free text, always with
  `cardinality` and `conditioned_on` set to keep cost down.
- A fixed `meta.seed` for reproducibility.

Validate the recipe before you show it:

```bash
python "${CLAUDE_PLUGIN_ROOT}/engine/validate_recipe.py" "outputs/<slug>/recipe.yaml"
```

## Stage 3, present the recipe for review (confirmation gate)

Render and publish the recipe artifact:

```bash
python "${CLAUDE_PLUGIN_ROOT}/engine/render.py" recipe \
  "outputs/<slug>/recipe.yaml" "outputs/<slug>/recipe.html"
```

Publish `recipe.html` as an **Artifact** (tables of every column with its
distribution, correlation and conditional badges, constraints, entity diagram).
In chat, summarize: tables and row counts, the key relationships encoded,
anything using the LLM, and the seed. **Ask the user to confirm or amend before
generating.** Note the expected LLM cost and row count if there are text columns.

## Stage 4, generate

Run the engine. It builds each table deterministically, links via the shared
keys, enforces constraints (resample, clip, drop), and fills text columns in
batched parallel API calls (cached on disk).

```bash
python "${CLAUDE_PLUGIN_ROOT}/engine/generate.py" \
  --recipe "outputs/<slug>/recipe.yaml" \
  --out    "outputs/<slug>" \
  [--rows-scale 0.1]   # quick preview at 10% size, optional
  [--offline]          # skip LLM, use placeholders
  [--only customers,spendings]   # subset of tables
```

For very large runs or independent tables you can fan out generation per table
with the Agent tool (each agent runs `generate.py --only <table>`), but the
single-process engine already parallelizes the LLM calls and handles
inheritance ordering, so prefer one call unless tables are independent and huge.

**Recommended flow:** run once with `--rows-scale 0.1` (or `--offline`) as a
fast preview, show the validation report, then do the full run once the user
confirms.

## Stage 5, validate and present results

Render and publish the validation report:

```bash
python "${CLAUDE_PLUGIN_ROOT}/engine/render.py" report \
  "outputs/<slug>/generation_report.json" "outputs/<slug>/report.html"
```

Publish `report.html` as an **Artifact**. It shows per-column summary stats,
distribution-fidelity checks against the recipe, categorical drift, and
foreign-key integrity. In chat: confirm row counts, FK integrity (it should be
clean), constraint satisfaction, and point to the CSV files. Call out any
warnings.

## Confirmation gates (do not skip)

1. After the **spec**, the user validates the grounded research.
2. After the **recipe**, the user validates the generation contract.

Generation only runs after gate 2. Mention LLM usage and cost before incurring
it.

## Reference files

- `recipe_template.yaml` annotated reference for every recipe feature.
- `${CLAUDE_PLUGIN_ROOT}/engine/recipe.schema.json` recipe JSON schema.
- `${CLAUDE_PLUGIN_ROOT}/engine/generate.py` the generation engine.
- `${CLAUDE_PLUGIN_ROOT}/engine/render.py` `spec`, `recipe`, and `report` renderers.
- `${CLAUDE_PLUGIN_ROOT}/engine/validate_recipe.py` standalone recipe validator.
