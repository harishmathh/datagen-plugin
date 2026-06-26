# Domain Research Report, {{BUSINESS_NAME}}

> **Status:** for review · **Generated:** {{DATE}} · **Confidence:** {{CONFIDENCE}}
> This is a text mirror of the research. The visual version is
> `research_report.html`, built from `research.json`. Every non-obvious number
> carries a citation. This is research only: it does not propose datasets and it
> does not design any schema.

---

## 1. Request summary

| Field | Value |
|---|---|
| Business context | {{ONE_LINE_CONTEXT}} |
| Objective | {{OBJECTIVE}} |
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

Who the customers actually are for this segment, industry, and geography.

- **Demographics:** age bands, gender split, household composition, income
  brackets, geographic distribution (with cited benchmarks).
- **Behavioral patterns:** purchase frequency, basket size, channel preference,
  digital engagement, loyalty and churn dynamics.
- **Known segments / archetypes** in this industry (from research) and how they
  typically differ on spend, frequency, and category mix.

| Segment archetype | Approx. share | Distinguishing traits | Source |
|---|---|---|---|
| … | … | … | … |

## 4. Domain metrics & distributions

The statistical shape of each key quantity, grounded in research.

| Metric | Distribution shape | Params (grounded) | Rationale / source |
|---|---|---|---|
| Annual spend | log-normal / right-skewed | median ~$X, p95 ~$Y | retail spend is heavy-tailed [src] |
| Order frequency | Poisson | λ ≈ … | … |
| … | … | … | … |

## 5. Relationships & constraints

Real-world dependencies that keep the picture internally consistent.

- **Correlations:** e.g. spend rises with frequency (rho about 0.5 to 0.7);
  premium share rises with income; engagement falls with age.
- **Conditional logic:** e.g. families have larger baskets and more weekend
  visits; young singles have higher app usage and lower spend.
- **Hard constraints:** e.g. `num_children < household_size`; `spend >= 0`;
  `tenure_months <= age*12`.
- **Outliers / edge cases:** whales, dormant accounts, returns-heavy customers,
  each with a realistic prevalence.

## 6. Open questions for the user

Anything ambiguous or where research disagreed with the prompt and a human
decision is needed.

- [ ] …

## 7. Sources

A numbered list of every source consulted, with what was drawn from each.

1. [Title]({{URL}}), used for: …
2. …

---
*Confidence note:* where research was thin or sources conflicted, this is stated
inline rather than papered over.
