---
name: Dataset-Research
description: A standalone domain-research skill. Given a business context and an objective (plus optional comments), it fans out parallel web research to validate the business's numbers (revenue, store count, CAGR, ROI, channel mix), profile its real customer base and segments, and derive grounded statistical shapes, relationships, and constraints. It writes one compact research.json and renders a beautiful, illustrated HTML report for you to read. Use this whenever you just want the research: "research the domain for this business", "validate these numbers", "what does the real customer base look like for X", "profile customers so they can be segmented". It does research only and then stops. It never proposes datasets, writes a recipe, or generates data. Dataset-Generator calls this skill to get its grounded inputs.
---

# Dataset-Research

This skill researches the real-world domain behind a business and writes up what
it found, as a visual report. That is the whole job. It does **not** propose
datasets, design any schema, build a recipe, or generate data. If the user wants
data, that is Dataset-Generator, which calls this skill first and then takes
over.

The company described can be made up, but it stands for a real *kind* of
business. So before any number is used, this skill checks it against comparable
real companies and published benchmarks.

## Required inputs (hard gate)

Two inputs are mandatory, one is optional:

1. **Business context** (required) the company and what it does.
2. **Objective** (required) what the research is for, for example "understand
   the customer base well enough to segment it into 4 to 6 groups".
3. **Additional comments** (optional) geography, focus areas, size of the
   operation, special concerns.

If the business context or the objective is missing or vague, **stop and ask the
user for it.** Do not start researching, do not guess, do not fill in a
plausible default. Say plainly what is missing and wait. Comments are optional;
if there are none, proceed. This is a hard gate.

Note what this skill does *not* take: it never asks "which datasets" or "what
sizes". Those are generation questions and have no place here. The objective is
about understanding, not output tables.

## Where the output goes

Make one run directory `outputs/<slug>/`, where `<slug>` is
`<business-name>-<YYYYMMDD>` in kebab-case, no spaces. Everything for this run
lives there:

- `outputs/<slug>/research.json` the structured research artifact. This is the
  machine-readable backing file, validated against
  `${CLAUDE_PLUGIN_ROOT}/engine/research_schema.json`. It is what
  Dataset-Generator picks up when this skill runs as its first step.
- `outputs/<slug>/research_report.html` the visual, illustrated report you show
  the user. Built from `research.json`.
- `outputs/<slug>/spec.md` an optional human-readable mirror of the research,
  filled from `spec_template.md`. Nice to have for diffing; not required for the
  HTML.

The user reads the HTML. Keep the JSON small and structured: the model emits
data, the Python builder does the visual layout. That is the token-efficiency
win, do not hand-author HTML.

## How to run it

### 1. Read the request back

Restate the business context and the objective in three or four lines so the
user can catch a misreading early. List the specific claimed numbers worth
checking: revenue, store or branch count, customer base size, CAGR, ROI, channel
or segment mix, geography.

### 2. Fan out the web research (parallel agents)

Spawn the prebuilt research agents in parallel, in a single message with several
Agent calls, using the `agentType` shown. Each owns one aspect, uses WebSearch
and WebFetch, and returns a compact cited JSON fragment. Hand each one the
business context, the objective, and any comments, in two or three lines. Do not
paste long instructions; the agent definitions already hold them.

| agentType | Owns | Returns |
|---|---|---|
| `business-benchmarks` | revenue, store count, revenue per unit, CAGR, ROI | `attributes`, `sanity_checks` |
| `customer-demographics` | age, gender, income, household, geography splits | `demographics` |
| `customer-behavior` | frequency, basket, channel, loyalty, churn, segments | `behavior`, `segments` |
| `metric-distributions` | distribution shapes, params, relationships | `metrics`, `relationships` |
| `qualitative-signal` | forums, reviews, case studies, real-company texture | `summary`, extra `conditionals`, `outliers`, `open_questions` |

For a segmentation objective, lean on `customer-behavior` and
`metric-distributions` for the segment archetypes and the variables that
separate them.

> If the `deep-research` skill is available and the user wants maximum rigor, you
> can hand the web phase to it instead. Otherwise the agent fan-out above is the
> default and the cheaper path.

### 3. Reconcile and assemble research.json

Merge the fragments into one `research.json` that validates against
`engine/research_schema.json`. For each claimed number, settle on one grounded
value: keep it (plausible), adjust it and say why (adjust), or flag it
(unverifiable). Run the cross-checks (revenue / stores, revenue / customers).
Where sources disagree, say so in the field rather than smoothing it over. Make
sure demographic and segment shares are plain numbers that add up to about 100,
the charts depend on it. Set `generated` to today's date and `confidence` to
high, medium, or low based on how much was verifiable.

Validate it:

```bash
python "${CLAUDE_PLUGIN_ROOT}/engine/validate_research.py" \
  "outputs/<slug>/research.json"
```

This checks the JSON against `research_schema.json`. If `jsonschema` is not
installed it falls back to a light key check, so it always gives a signal. The
renderer is also forgiving of missing optional fields.

### 4. Render the report and show it

```bash
python "${CLAUDE_PLUGIN_ROOT}/engine/render.py" research \
  "outputs/<slug>/research.json" "outputs/<slug>/research_report.html"
```

Publish `outputs/<slug>/research_report.html` as an **Artifact** so the user
reads it visually: hero header, KPI cards, verdict pills, donut and bar charts
for demographics and segments, distribution sparklines, and a sources panel. In
chat, give a tight summary: the three or four most important grounded numbers,
anything you changed from what the prompt claimed, and the open questions.

Optionally also fill `spec_template.md` into `outputs/<slug>/spec.md` for a
diffable text record. Skip it if the user only wants the visual.

### 5. Stop

That is the end of a standalone run. Do not propose datasets, do not build a
recipe, do not generate data. If the user wants the actual dataset, that is
Dataset-Generator, which will call this skill for the research part and then take
over.

When this skill is run *by* Dataset-Generator, it still stops here, but it hands
the `research.json` path back so generation can take over.

## Quality bar

- No bare domain number. "Roughly $X, the industry median per [source]" beats a
  confident figure with nothing behind it.
- Distributions are shapes with parameters, not adjectives. Write `lognormal,
  median ~$420, p95 ~$2100`, not "skewed".
- Capture relationships and constraints now. They are painful to recover later.
- Be honest about thin spots. A weak assumption flagged is worth more than a
  guess hidden, because anything built on this research inherits it.

## Reference files

- `${CLAUDE_PLUGIN_ROOT}/engine/research_schema.json` the shape of research.json.
- `${CLAUDE_PLUGIN_ROOT}/engine/validate_research.py` validates research.json.
- `${CLAUDE_PLUGIN_ROOT}/engine/render.py` `research` mode renders the report.
- `${CLAUDE_PLUGIN_ROOT}/engine/build_research_report.py` the HTML builder.
- `spec_template.md` optional human-readable text mirror.
- `${CLAUDE_PLUGIN_ROOT}/agents/` the five research agents.
