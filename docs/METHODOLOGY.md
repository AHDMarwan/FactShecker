# Methodology v0.2

FactShecker is a monitoring and triage system, not an autonomous fact-checking authority.

## 1. Evidence-support score

The collector groups similar monitored news headlines and computes an **evidence-support score** from three observable signals:

1. the strongest configured source weight in the cluster;
2. the number of distinct non-fact-check sources covering a similar claim or event;
3. limited language diversity across those monitored feeds.

The current score is:

```text
score = 0.45 * best_source_weight
      + 0.45 * corroboration
      + 0.10 * language_diversity
```

This score is **not** a probability that a statement is true. A high score only means that the monitored public feeds contain stronger and more diverse coverage of the same or a similar headline.

Fact-checking outlets are deliberately excluded from corroboration. A fact-check article may refute, qualify, or contextualize a claim, so counting it as another supporting source would be methodologically wrong.

## 2. Automated statuses

- `needs_review`: only one distinct supporting source is currently visible in the cluster.
- `medium_evidence`: at least two distinct supporting sources are visible.
- `corroborated`: at least three distinct supporting sources are visible and the evidence-support score is at least 0.70.

These are triage labels. They are not verdicts such as true, false, misleading, or manipulated.

## 3. Claim-candidate score

Version 0.2 adds a lightweight **claim score** for deciding whether a headline is worth sending to a human fact-check queue. It uses observable headline features only:

- reporting/assertion verbs;
- event verbs;
- numeric or quantified details;
- enough specificity to form a factual statement;
- penalties for questions, opinion, commentary, and analysis framing.

A headline with a score of at least `0.35` is marked as a claim candidate. The score measures **check-worthiness heuristics**, not truthfulness.

## 4. Previously fact-checked claim matching

Articles from configured `fact_checker` sources are stored separately from ordinary news coverage. Each news cluster is compared with those fact-check titles using:

- normalized character-level similarity;
- token Jaccard overlap;
- a small same-language bonus.

Matches below `0.46` are discarded and at most three are shown per cluster.

A match means only that the wording/topics appear related. It does **not** mean that the verdict in the older fact-check automatically applies to the current claim. Dates, entities, quantities, geography, and context must still be checked by a human reviewer.

This separation mirrors the distinction between identifying check-worthy claims and retrieving previously fact-checked claims in established fact-checking research tasks.

## 5. Source roles

Configured sources have roles rather than universal truth labels:

- `official` / `primary_institution`: useful as primary evidence for statements about that institution;
- `news_agency`, `public_broadcaster`, `newsroom`: reporting sources used for coverage/corroboration signals;
- `fact_checker`: verification material, kept separate from corroboration;
- `unrated`: discovered source without a curated profile.

A high configured source weight does not make every statement from that source true. It only affects the current triage heuristic and must be interpreted in context.

## 6. Human fact-checking standard

A final verdict should require a reviewer to inspect the original claim, identify the best primary evidence available, check dates and context, consider counter-evidence, and record the reasoning and sources used.

The project is intentionally aligned with established fact-checking principles such as transparent sourcing, reproducible evidence, corrections, and avoiding unsupported verdicts.

Useful references:

- AFP Fact Check — How we work: https://factcheck.afp.com/How-we-work
- Africa Check — How we fact-check: https://www.africacheck.org/how-we-fact-check
- Africa Check — How we rate claims: https://africacheck.org/how-we-fact-check/how-we-rate-claims
- IFCN Code of Principles: https://ifcncodeofprinciples.poynter.org/
- CLEF CheckThat! Lab: https://arxiv.org/abs/2109.12987

## Current limitations

Version 0.2 still clusters and matches headlines mainly with lexical similarity. It does not yet retrieve full article bodies, perform multilingual embeddings, verify images/video, establish full source independence, resolve temporal contradictions, or issue human-reviewed public verdicts.

Cross-language semantic matching should be added only after benchmark evaluation, because lexical similarity alone is weak across Arabic, French, and English.
