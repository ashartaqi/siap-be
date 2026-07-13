# Ask SIAP — Phase 2.5 Findings: Hybrid Retrieval Fix & Regression

**Date:** July 2026
**Branch:** TBD (pending decision — see open items)
**Context:** Follow-up to `PHASE2_FINDINGS.md`, which identified pure semantic
retrieval as unable to reliably surface hard constraints (age, position,
preferred foot). This document covers the hybrid SQL-filter + vector-rerank
implementation, a regression found and fixed during testing, and an updated
RAGAS comparison.

---

## 1. What was built

- `constraint_extractor.py` — Gemini 2.5 Flash call that extracts structured
  filters (position, age range, preferred foot, nationality, overall rating,
  stat thresholds) from a natural-language question. Fails open (returns `{}`)
  on any error, so extraction failures degrade to pure vector search rather
  than breaking retrieval.
- `player_filters.py` — converts extracted constraints into a SQLAlchemy
  query against `Player`/`PlayerPos`/`PlayerStats`/`GoalkeeperStats`, returning
  a candidate ID list (or `None` if no usable constraints were found).
- `retrieval.py` — updated to SQL-filter first (when constraints exist), then
  rank the filtered candidate set by pgvector cosine similarity.

## 2. Regression found and fixed

Initial hybrid retrieval testing caused **faithfulness to drop from ~0.92 to
0.64** and **answer relevancy to drop from ~0.75 to 0.33** — a real
regression, not noise.

**Root cause:** the constraint extractor returned `"AM"` for "attacking
midfielder," but the actual schema stores this position as `"CAM"`
(confirmed via `SELECT DISTINCT position FROM positions`). The mismatched
value caused the SQL filter to return zero candidates, producing an empty
context and a "no data provided" answer for a valid, well-populated position.

**Fix:** the extraction prompt now includes an explicit whitelist of valid
position codes (`CB, LB, RB, CDM, CM, CAM, LM, RM, LW, RW, CF, ST, GK`).
`player_filters.py` also defensively drops any position values outside this
set, so a future prompt regression degrades to "no position filter" instead
of silently zeroing results. Additionally, the extractor's fail-open
exception handler now logs a warning instead of swallowing errors silently —
this gap caused a false lead during debugging (a rate-limit 429 looked
identical to "the model found no constraints").

## 3. RAGAS comparison

| Metric | Phase 2 (baseline) | Post-hybrid (regression) | Post-hybrid (fixed) |
|---|---|---|---|
| Context precision | 0.0 | 0.0 | 0.0 |
| Context recall | 0.0 | 0.0 | 0.0 |
| Faithfulness | ~0.92 | 0.64 | **0.975** |
| Answer relevancy | ~0.75 | 0.33 | 0.0* |

\*Answer relevancy scored `NaN`/0 on most rows in this run. This correlates
with hedged, refusal-style answers (see §4) rather than appearing to be a
new regression — flagged as a metric artifact worth investigating further,
not yet fully explained.

Note: 5 of 20 judge-model calls (Groq free tier) hit `TimeoutError` during
this run. Retried automatically by RAGAS's job runner; results should be
treated as directionally reliable, not perfectly clean.

## 4. Honest interpretation

- **The CAM bug fix is confirmed working** — verified in isolation
  (`extract_constraints` now returns `{'positions': ['CAM']}`) and via the
  eval (question 5 now returns real, valid CAM players instead of an empty
  context).
- **Context precision/recall remain at 0.0**, and this fix was not expected
  to change that. Of the 5 eval questions, only 1 (the CAM one) involved a
  hard constraint value that was previously mismatched. The other 4 fail for
  a different, unaddressed reason: **superlative queries with no explicit
  threshold** ("fast," "best," "high rating"). The extractor correctly
  declines to invent an arbitrary number when none is stated, so no SQL
  filter narrows these — leaving retrieval entirely dependent on vector
  similarity, which was already known to be weak for this kind of ranking.
- **Hybrid retrieval works as designed for explicit hard constraints** —
  confirmed independently by hand (e.g. "centre backs over 30 with 85+
  defending" returned 5/5 correct results on all three constraints).

## 5. Open items / next steps

1. Decide how to handle superlative queries — options include: a secondary
   LLM pass that infers a reasonable implicit threshold when the user's
   intent is clearly "top N by some stat" (e.g. "best reflexes" → sort by
   the stat directly rather than filter), or reframing this as a distinct
   query type handled outside the constraint-extraction path entirely.
2. Investigate the answer relevancy metric behavior on hedged/refusal
   answers before trusting it as a headline number.
3. Branch/PR strategy: fold into the still-unmerged Phase 1 PR, or open a
   separate PR scoped to this fix — undecided.
4. Consider a cheap pre-check to skip the constraint-extraction call
   entirely for obviously unconstrained questions, to reduce Gemini calls
   per query (currently 2 per question) given free-tier daily caps.