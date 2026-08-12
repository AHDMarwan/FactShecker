# Methodology v0.1

FactShecker is a monitoring and triage system, not an autonomous fact-checking authority.

## What the automated score means

The collector groups similar monitored headlines and computes an **evidence-support score** from three observable signals:

1. the strongest configured source weight in the cluster;
2. the number of distinct sources covering a similar claim or event;
3. limited language diversity across the monitored feeds.

The current score is:

```text
score = 0.45 * best_source_weight
      + 0.45 * corroboration
      + 0.10 * language_diversity
```

This score is **not** a probability that a statement is true. A high score only means that the monitored public feeds contain stronger and more diverse support for the same or a similar headline.

## Automated statuses

- `needs_review`: only one distinct source is currently visible in the cluster.
- `medium_evidence`: at least two distinct sources are visible.
- `corroborated`: at least three distinct sources are visible and the evidence-support score is at least 0.70.

These are triage labels. They are not verdicts such as true, false, misleading, or manipulated.

## Human fact-checking standard

A final verdict should require a reviewer to inspect the original claim, identify the best primary evidence available, check dates and context, consider counter-evidence, and record the reasoning and sources used.

The project is intentionally aligned with established fact-checking principles such as transparent sourcing, reproducible evidence, corrections, and avoiding unsupported verdicts.

Useful references:

- AFP Fact Check — How we work: https://factcheck.afp.com/How-we-work
- Africa Check — How we fact-check: https://www.africacheck.org/how-we-fact-check
- Africa Check — How we rate claims: https://africacheck.org/how-we-fact-check/how-we-rate-claims
- IFCN Code of Principles: https://ifcncodeofprinciples.poynter.org/

## Current limitations

Version 0.1 clusters headlines mainly with character-level similarity. It does not yet perform multilingual semantic claim matching, article-body retrieval, image/video verification, source independence analysis, or a human-review publishing workflow.

Those features should be added incrementally and evaluated on a labeled benchmark before they affect public-facing verdicts.
