---
description: Generate a synthetic but realistic dataset for a business. Runs research, then a reviewable recipe, then the seeded engine.
argument-hint: <business context> | objective: <...> | comments: which datasets, sizes, special needs
---

Run the **Dataset-Generator** skill.

This is the full pipeline: it calls Dataset-Research to ground the domain, then
compiles a reviewable YAML recipe, then builds the linked datasets with the
seeded Python engine. There is a review gate after the research and after the
recipe.

The user's request follows. Pull the business context and the objective out of
it; comments should say which datasets to produce, their sizes, and anything
special. If the business context or the objective is missing, ask for it and
wait before doing anything else.

User request:
$ARGUMENTS
