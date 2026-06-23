# DataGen — research-grounded synthetic dataset generator

A [Claude Code](https://claude.com/claude-code) plugin that turns a plain-English
**business context + objective** into **synthetic yet realistic datasets**.

It doesn't just emit random numbers. It first *researches the real-world domain*
on the web to ground every figure, gets you to validate a spec, compiles a
human-readable YAML "recipe," lets you review it, then builds the data with a
deterministic Python engine — distributions, correlations, conditional logic,
hard constraints, multi-table referential integrity, and LLM-authored text.

## The two skills

| Skill | What it does |
|---|---|
| **Dataset-Research** | Fans out parallel web research to validate the business's numbers (revenue, store count, CAGR, ROI, channel mix), profile its real customer base and segments, and derive grounded distributions, relationships, and constraints. Produces a standardized `spec.md` + an HTML review artifact. |
| **Dataset-Generator** | Wraps Dataset-Research, then compiles the confirmed spec into a `recipe.yaml`, presents it for review, and runs the engine to produce linked CSVs + a validation report. |

`Dataset-Research` is **step 1 of** `Dataset-Generator`, but can run standalone.

## Pipeline

```
business context ─▶ ① RESEARCH ─▶ spec.md  ─(you confirm)─▶
                  ② RECIPE   ─▶ recipe.yaml ─(you confirm)─▶
                  ③ GENERATE ─▶ *.csv + validation report
```

Two human review gates: after the **spec** (is the research right?) and after
the **recipe** (is the generation contract right?). Generation only runs after
the second gate.

## Install

```
/plugin marketplace add HarishMaths1972/datagen-plugin
/plugin install datagen
```

Then just describe what you want:

> Generate customers, spendings, engagement, and household datasets for
> BrightBasket Retail — a mid-size grocery chain... (objective: segment the
> customer base into 4–6 groups).

## Engine features

The generation engine (`plugins/datagen/engine/`) reads a recipe and emits one
CSV per dataset, fully **seeded/reproducible**:

- **Distributions:** normal, lognormal, uniform, exponential, poisson, beta,
  gamma, pareto, zipf, bernoulli, weighted categorical, constant, and datetime
  (uniform or with monthly/weekday **seasonality**).
- **Relationships:** induced numeric **correlation** (Gaussian-copula,
  marginal-preserving), **conditional** distributions keyed on another column,
  **derived** columns via a sandboxed expression evaluator, and cross-table
  column **inheritance**.
- **Multi-table referential integrity:** shared **entity** id pools with 1:1
  primary keys and many:1 **foreign keys**, so all tables join cleanly.
- **Constraints:** boolean expressions enforced per row with `resample` / `clip`
  / `drop` / `error` repair.
- **Outliers & missingness:** realistic tails and nullable fractions.
- **Text columns:** `faker` for structured text (names/cities/emails) and
  `type: text` for LLM-authored free text via the Anthropic API — batched,
  concurrent, on-disk cached, with `cardinality` cost control. Degrades to
  clearly-marked placeholders offline.
- **Validation report:** per-column stats, distribution-fidelity vs the recipe,
  categorical drift, and FK-integrity checks — rendered as an HTML artifact.

## Requirements

- Python 3.10+ with `numpy`, `pandas`, `PyYAML` (required). `jsonschema`,
  `Faker`, and `anthropic` are optional — the engine degrades gracefully.
- `ANTHROPIC_API_KEY` only needed for `type: text` columns.

```
pip install -r plugins/datagen/requirements.txt
```

## Using the engine directly

```bash
# validate a recipe
python plugins/datagen/engine/validate_recipe.py recipe.yaml

# generate (10% preview, offline)
python plugins/datagen/engine/generate.py --recipe recipe.yaml --out outputs/run \
       --rows-scale 0.1 --offline

# render review artifacts
python plugins/datagen/engine/render.py recipe recipe.yaml recipe.html
python plugins/datagen/engine/render.py report outputs/run/generation_report.json report.html
```

See [`recipe_template.yaml`](plugins/datagen/skills/dataset-generator/recipe_template.yaml)
for an annotated reference of every recipe feature, and
[`recipe.schema.json`](plugins/datagen/engine/recipe.schema.json) for the
authoritative schema.

## Repository layout

```
.claude-plugin/marketplace.json      marketplace manifest
plugins/datagen/
  .claude-plugin/plugin.json         plugin manifest
  skills/dataset-research/           SKILL.md, spec_template.md
  skills/dataset-generator/          SKILL.md, recipe_template.yaml
  engine/                            generate.py, distributions, constraints,
                                     relations, tables, llm_text, faker_cols,
                                     safe_eval, validate, render, schema, tests
  requirements.txt
```

## License

MIT — see [LICENSE](LICENSE).
