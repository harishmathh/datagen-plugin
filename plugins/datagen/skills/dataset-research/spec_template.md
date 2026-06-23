# Dataset Research Spec — {{BUSINESS_NAME}}

> **Status:** DRAFT for review · **Generated:** {{DATE}} · **Spec version:** 1.0
> This document grounds the synthetic-dataset request in real-world data. Every
> non-obvious number carries a citation. Review the assumptions, correct
> anything off, then confirm to proceed to recipe compilation.

---

## 1. Request summary

| Field | Value |
|---|---|
| Business context | {{ONE_LINE_CONTEXT}} |
| Objective | {{OBJECTIVE}} |
| Requested datasets | {{REQUESTED_DATASETS}} |
| Additional comments | {{COMMENTS}} |

## 2. Business profile (researched)

A short narrative of what this kind of business actually looks like, with the
plausibility of every figure in the prompt assessed against comparable real
companies. Mark each as **Plausible**, **Adjust to X**, or **Unverifiable**.

| Attribute | Stated in prompt | Real-world range (researched) | Verdict | Source |
|---|---|---|---|---|
| Annual revenue | {{STATED}} | {{RANGE}} | {{VERDICT}} | [{{SRC}}]({{URL}}) |
| Store count | … | … | … | … |
| Revenue / store | (derived) | … | … | … |
| CAGR | … | … | … | … |
| Marketing ROI | … | … | … | … |
| Channel mix | … | … | … | … |

> **Derived sanity checks:** e.g. revenue ÷ stores = $X/store vs industry $Y/store;
> revenue ÷ customers = $Z annual spend per shopper vs benchmark.

## 3. Customer base (researched)

Who the customers actually are for this segment/industry/geography. This feeds
the demographic and behavioral distributions in the recipe.

- **Demographics:** age bands, gender split, household composition, income
  brackets, geographic distribution (with cited benchmarks).
- **Behavioral patterns:** purchase frequency, basket size, channel preference,
  digital engagement, loyalty/churn dynamics.
- **Known segments / archetypes** in this industry (from research) and how they
  typically differ on spend, frequency, and category mix.

| Segment archetype | Approx. share | Distinguishing traits | Source |
|---|---|---|---|
| … | … | … | … |

## 4. Domain metrics & distributions

The statistical shape of each key quantity, grounded in research, that the
recipe will encode.

| Metric | Distribution shape | Params (grounded) | Rationale / source |
|---|---|---|---|
| Annual spend | log-normal / right-skewed | median ~$X, p95 ~$Y | retail spend is heavy-tailed [src] |
| Order frequency | Poisson | λ ≈ … | … |
| … | … | … | … |

## 5. Relationships & constraints

Real-world dependencies the data must respect, so the synthetic data is
internally consistent (not just marginally realistic).

- **Correlations:** e.g. spend ↑ with frequency (ρ≈0.5–0.7); premium share ↑
  with income; engagement ↓ with age.
- **Conditional logic:** e.g. families → larger baskets, more weekend visits;
  young singles → higher app usage, lower spend.
- **Hard constraints:** e.g. `num_children < household_size`; `spend >= 0`;
  `tenure_months <= age*12`.
- **Outliers / edge cases:** whales, dormant accounts, returns-heavy customers —
  with realistic prevalence.

## 6. Proposed dataset blueprint

One subsection per requested dataset. This is the bridge to the recipe.

### {{DATASET_NAME}}
- **Grain:** one row per …
- **Keyed on / links to:** …
- **Suggested size:** … (rationale: sampled from the {{POP}} population)
- **Columns:** name · type · meaning · grounded distribution · relationships

| Column | Type | Meaning | Distribution | Depends on |
|---|---|---|---|---|
| … | … | … | … | … |

## 7. Open questions for the user

Anything ambiguous or where research disagreed with the prompt and a human
decision is needed before generating.

- [ ] …

## 8. Sources

A numbered list of every source consulted, with what was drawn from each.

1. [Title]({{URL}}) — used for: …
2. …

---
*Confidence note:* where research was thin or sources conflicted, this is stated
inline rather than papered over. Synthetic data inherits the quality of these
assumptions.
