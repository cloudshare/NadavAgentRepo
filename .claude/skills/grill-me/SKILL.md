---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
attribution: https://github.com/mattpocock/skills/blob/main/grill-me/SKILL.md
---

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time.

If a question can be answered by exploring the codebase, explore the codebase instead.

As you go, maintain a running Q&A document in the relevant project directory (e.g. `docs/<topic>-design-decisions.md`). Create it before the first question and update it after each answer. Each entry should capture the question, the decision made, and the reasoning. Mark deferred items clearly. At the end, include the full implementation plan derived from the decisions.
