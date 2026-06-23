---
name: Dataset-Research
description: Research the real-world domain behind a synthetic-data request and produce a grounded, reviewable spec. Given a business context, an objective, and optional comments, fan out web research to validate the business's numbers (revenue, store count, CAGR, ROI, channel mix), profile its real customer base and segments, and derive grounded statistical distributions, relationships, and constraints. Outputs a standardized spec.md plus an HTML review artifact. Use when the user wants to generate a realistic synthetic dataset and the domain must be grounded in reality first — this is step 1 of Dataset-Generator. Triggers on requests like "research the domain for this dataset", "validate these business numbers", or as the first phase of generating a dataset from a business context.
---

# Dataset-Research

Turn a business context + objective into a **research-grounded specification**
for synthetic data. The company may be fictional, but it represents a real
*kind* of business — so every number is checked against comparable real
companies and industry benchmarks before it drives data generation.

This skill is **step 1 of the Dataset-Generator workflow** but can also run
standalone. Its only deliverable is a reviewed `spec.md`.

## Inputs

Collect three things (ask if missing):
1. **Business context** — the company description.
2. **Objective** — what the dataset is for (e.g. "segment customers into 4–6 groups").
3. **Additional comments** — e.g. which datasets to produce, size, special needs.

## Output location

Create a run directory: `outputs/<slug>/` where `<slug>` is
`<business-name>-<YYYYMMDD>` (kebab-case, no spaces). All artifacts for this
run live here. Write:
- `outputs/<slug>/spec.md` — the standardized spec (fill `spec_template.md`).
- `outputs/<slug>/spec.html` — the review artifact (via `render.py`).
- `outputs/<slug>/research_notes/` — raw agent findings (optional, for audit).

## Procedure

### 1. Parse & restate the request
Extract the business attributes, the objective, and the requested datasets.
Restate them back to the user in 3–4 lines so they can catch misreadings early.
Identify the key claimed numbers that need validation (revenue, store/branch
count, customer base, CAGR, ROI, channel/segment mix, geography).

### 2. Fan out parallel research (use the Agent tool)
Spawn **independent research agents in parallel** (one message, multiple Agent
calls), each owning one aspect. Each agent uses `WebSearch` + `WebFetch` and
returns structured findings with citations. Suggested split (adapt to the
domain):

- **Agent A — Business benchmarks.** Validate revenue, store count, revenue per
  store, CAGR, growth model, and marketing ROI against comparable real
  companies and industry reports. Return: each claimed number, a realistic
  range, a verdict (plausible / adjust-to-X / unverifiable), and sources.
- **Agent B — Customer demographics.** Who shops at this kind of business in
  this geography? Age bands, gender split, household composition, income
  brackets, urban/rural or tier split — with cited benchmarks.
- **Agent C — Customer behavior & segments.** Purchase frequency, basket size,
  channel preference, digital engagement, loyalty/churn, and the *known
  segment archetypes* in this industry with approximate shares and traits.
- **Agent D — Metric distributions & relationships.** The statistical *shape* of
  key quantities (spend is right-skewed/log-normal, frequency ~Poisson, etc.),
  plausible parameters, and real correlations/dependencies (spend↔frequency,
  income↔premium-share, age↔digital-engagement).
- **Agent E — Community / qualitative signal.** Reddit, forums, case studies,
  and company pages of *similar* real companies for texture the numbers miss.

Give every agent the **objective** too, so research stays relevant (e.g. for a
segmentation objective, prioritize segment archetypes and discriminating
variables).

Tell each agent to return a compact, **cited** result (claim → value/range →
source URL). Prefer primary sources and recent data (it is currently 2026).

> If the `deep-research` skill is available and the user wants maximum rigor,
> you may delegate the web phase to it; otherwise the parallel Agent fan-out
> above is the default.

### 3. Reconcile & ground
Merge the agents' findings. For every claimed number, decide a **grounded
value** to use downstream: keep it if plausible, adjust it (and say why) if
research disagrees, or flag it if unverifiable. Run derived sanity checks
(revenue ÷ stores, revenue ÷ customers, etc.). Note conflicts honestly rather
than smoothing them over.

### 4. Write the spec
Fill `spec_template.md` (in this skill's directory) into
`outputs/<slug>/spec.md`. Every section must be completed; every non-obvious
number must carry a citation. Section 6 (dataset blueprint) is the bridge to the
recipe — for each requested dataset, propose grain, key/links, size, and the
column list with grounded distributions and relationships. Section 7 lists open
questions for the user.

### 5. Render & present for review
Render the HTML review artifact and present it:

```bash
python "${CLAUDE_PLUGIN_ROOT}/engine/render.py" spec \
  "outputs/<slug>/spec.md" "outputs/<slug>/spec.html"
```

Then publish `outputs/<slug>/spec.html` as an **Artifact** so the user can read
it visually (tables, verdict pills, sources). In chat, give a tight summary:
the 3–4 most important grounded numbers, anything you adjusted from the prompt,
and the open questions.

### 6. Confirm before proceeding
**Stop and ask the user to validate the spec.** Explicitly surface: (a) numbers
you changed from their prompt, (b) the proposed dataset blueprint, (c) open
questions. Only once they confirm (or amend) is the spec final. If this skill
was invoked as part of Dataset-Generator, hand the confirmed `spec.md` path
back so recipe compilation can begin.

## Quality bar
- No uncited domain number. "Roughly $X (industry median per [source])" beats a
  confident bare figure.
- Distributions are *shapes with parameters*, not just adjectives — the recipe
  needs `mean`/`std`/`lambda`, etc.
- Relationships and constraints are captured now; they are hard to retrofit.
- Be explicit about low-confidence areas. Synthetic data inherits these
  assumptions.

## Reference files
- `spec_template.md` — the exact spec structure to fill.
- `${CLAUDE_PLUGIN_ROOT}/engine/render.py` — `spec` mode renders the HTML.
