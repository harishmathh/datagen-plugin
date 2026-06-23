---
name: Dataset-Research
description: A standalone domain-research skill. Given a business context, an objective, and additional comments, it fans out web research to validate the business's numbers (revenue, store count, CAGR, ROI, channel mix), profile its real customer base and segments, and derive grounded statistical distributions, relationships, and constraints. It produces a visual HTML research report for you to read, backed by a spec file stored on disk. Use this when you just want the research: "research the domain for this business", "validate these numbers", "what does the real customer base look like for X". It does research only and stops there. Dataset-Generator calls this skill internally to get its grounded inputs, but on its own this skill never compiles a recipe or generates data.
---

# Dataset-Research

This skill researches the real-world domain behind a business and writes up what
it found. That is the whole job. It does not build a recipe and it does not
generate any data. If you want data at the end, use Dataset-Generator, which
calls this skill first and then takes over.

The company you describe can be made up, but it stands for a real *kind* of
business. So before any number gets used anywhere, this skill checks it against
comparable real companies and published benchmarks.

## Required inputs (do not skip this)

Three inputs are mandatory:

1. **Business context** the company and what it does.
2. **Objective** what the research is for (for example "understand the customer
   base so it can be segmented into 4 to 6 groups").
3. **Additional comments** anything else that matters: geography, which areas to
   focus on, size of the operation, special concerns.

If any of these three is missing or vague, **stop and ask the user for it.** Do
not start researching, do not guess, do not fill in a plausible default. List
exactly what is missing in plain language and wait. Only once all three are in
hand do you do anything else. This is a hard gate, not a suggestion.

## Where the output goes

Make one run directory: `outputs/<slug>/`, where `<slug>` is
`<business-name>-<YYYYMMDD>` in kebab-case with no spaces. Everything for this
run lives there:

- `outputs/<slug>/spec.md` the spec, stored internally. This is the structured
  record of the research. It is filled from `spec_template.md`.
- `outputs/<slug>/research_report.html` the visual report you actually show the
  user. Rendered from the spec.
- `outputs/<slug>/research_notes/` raw agent findings, kept for audit (optional).

The user reads the HTML. The `spec.md` is the machine-readable backing file, and
it is what Dataset-Generator picks up when this skill runs as its first step.

## How to run it

### 1. Read the request back

Pull out the business attributes, the objective, and anything in the comments.
Restate it in three or four lines so the user can catch a misreading early.
Pick out the specific claimed numbers that need checking: revenue, store or
branch count, customer base size, CAGR, ROI, channel or segment mix, geography.

### 2. Fan out the web research

Spawn independent research agents in parallel (one message, several Agent
calls). Each one owns a single aspect, uses WebSearch and WebFetch, and comes
back with cited findings. A split that works well, adapt it to the domain:

- **Agent A, business benchmarks.** Check revenue, store count, revenue per
  store, CAGR, growth pattern, and marketing ROI against comparable real
  companies and industry reports. Return, for each claimed number: a realistic
  range, a verdict (plausible / adjust to X / unverifiable), and sources.
- **Agent B, customer demographics.** Who actually shops at this kind of
  business in this geography? Age bands, gender split, household make-up, income
  brackets, urban or rural or tier split, each with a cited benchmark.
- **Agent C, customer behavior and segments.** Purchase frequency, basket size,
  channel preference, digital engagement, loyalty and churn, and the segment
  archetypes that are known in this industry, with rough shares and traits.
- **Agent D, metric distributions and relationships.** The statistical shape of
  the key quantities (spend tends to be right-skewed or log-normal, frequency is
  roughly Poisson, and so on), plausible parameters, and the real dependencies
  (spend with frequency, income with premium share, age with digital use).
- **Agent E, qualitative signal.** Reddit, forums, case studies, and the pages
  of similar real companies, for the texture the raw numbers miss.

Hand every agent the objective too, so the research stays pointed at what the
user actually wants. For a segmentation objective, for instance, push harder on
segment archetypes and the variables that separate them.

Tell each agent to return a compact, cited result: claim, then value or range,
then source URL. Prefer primary sources and recent data (it is 2026).

> If the `deep-research` skill is available and the user wants maximum rigor, you
> can hand the web phase to it instead. Otherwise the parallel Agent fan-out
> above is the default.

### 3. Reconcile and ground

Merge what the agents found. For each claimed number, settle on one grounded
value: keep it if it holds up, adjust it (and say why) if research disagrees, or
flag it if it cannot be verified. Run the obvious cross-checks (revenue divided
by stores, revenue divided by customers, and so on). Where sources disagree, say
so plainly instead of smoothing it over.

### 4. Write the spec (internal)

Fill `spec_template.md` (in this skill's directory) into
`outputs/<slug>/spec.md`. Complete every section. Every non-obvious number
carries a citation. Section 6, the dataset blueprint, is written so that *if*
someone later compiles a recipe from it they have what they need (grain, keys,
size, columns with grounded distributions and relationships); it is part of the
record either way. Section 7 lists open questions for the user.

### 5. Render the report and show it

Build the HTML report and present that:

```bash
python "${CLAUDE_PLUGIN_ROOT}/engine/render.py" spec \
  "outputs/<slug>/spec.md" "outputs/<slug>/research_report.html"
```

Publish `outputs/<slug>/research_report.html` as an **Artifact** so the user can
read it visually, with the tables, verdict pills, and sources laid out. In chat,
give a tight summary: the three or four most important grounded numbers, anything
you changed from what the prompt claimed, and the open questions.

### 6. Stop

That is the end of a standalone run. Do not start building a recipe and do not
generate data. If the user wants the actual dataset, that is Dataset-Generator's
job, and it will call this skill for the research part.

When this skill is being run *by* Dataset-Generator, it still stops here, but it
hands the confirmed `spec.md` path back so generation can take over.

## Quality bar

- No bare domain number. "Roughly $X, the industry median per [source]" beats a
  confident figure with nothing behind it.
- Distributions are shapes with parameters, not adjectives. A downstream recipe
  needs `mean`, `std`, `lambda`, not the word "skewed".
- Capture relationships and constraints now. They are painful to add later.
- Be honest about thin spots. Anything built on this research inherits these
  assumptions, so a weak assumption flagged is worth more than a guess hidden.

## Reference files

- `spec_template.md` the exact structure to fill.
- `${CLAUDE_PLUGIN_ROOT}/engine/render.py` the `spec` mode renders the HTML report.
