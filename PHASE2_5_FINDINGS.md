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

   ## 6. Sort-Intent Detection (Ranking Queries)

### 6.1 Motivation

After fixing the CAM position-whitelist regression (§2), context precision/recall
remained at 0.0. Manual inspection showed the CAM fix only addressed 1 of 5 eval
questions. The remaining 4 failed for a distinct reason: **superlative queries**
("fast," "best," "highest") with no explicit numeric threshold. The constraint
extractor correctly declines to invent a threshold when none is stated (per its
original design), but this left nothing for the SQL filter to act on, and pure
vector similarity was already a known-weak fit for "give me the actual top N by
this stat."

### 6.2 Design

Extended `constraint_extractor.py` to detect **sort intent** alongside hard
constraints: when a question asks for "best/top/fastest/highest" by some
quality, it now returns `sort_by` (a validated stat field) and `sort_direction`,
instead of guessing a threshold.

Added `build_ranked_player_ids()` in `player_filters.py`: applies any hard
filters first, then sorts directly in SQL (`ORDER BY <stat> LIMIT k`) and
returns the top-k IDs. `retrieval.py` checks this path first; if present, it
**skips vector search entirely** for that query — once the exact stat to rank
by is known, SQL ordering is strictly more correct than embedding similarity.

### 6.3 Manual verification (isolated, ground-truth-checked)

Two sort fields tested independently, each against ground truth from the
original Phase 2 SQL-derived eval set:

- **"Which goalkeepers have the best reflexes?"** → Sommer, ter Stegen,
  Courtois (90), Oblak, Alisson (89) — **exact match**, all 5 names and values,
  correct descending order (tie order among the three 90s not deterministic,
  not considered a bug).
- **"Who are the fastest strikers?"** → Mbappé (97), then four players tied at
  95 pace, all genuinely ST (some multi-position) — correct top pace values
  and order, confirmed by inspection.

Both confirm the two code branches (`PlayerStats` join and `GoalkeeperStats`
join) work correctly in isolation.

### 6.4 Full RAGAS re-run — results and a necessary caveat

```
{'context_precision': 0.30, 'context_recall': 0.00, 'faithfulness': 0.69, 'answer_relevancy': 0.46}
```

**This run had significant judge-model infrastructure failures**: 8 of 20
judge-scoring jobs failed (7 `TimeoutError`, plus Groq's `llama-3.3-70b`
**daily token quota** was exhausted mid-run — `Limit 100000, Used 99209`).
Failed judge calls produce `0`/`NaN` scores for that question-metric pair
regardless of whether retrieval was actually correct. This means the
aggregate numbers above likely **understate** real performance and should
not be taken as a clean signal on their own.

**Manual cross-check against ground truth (same method as §6.3), by question:**

| Question | Retrieved contexts vs. ground truth | Verdict |
|---|---|---|
| "best reflexes" (GKs) | Sommer, ter Stegen, Courtois, Oblak, Alisson — exact match | ✅ Perfect (scored only 0.2 precision — judge noise) |
| "high overall rating" (CAMs) | De Bruyne, Bernardo Silva, Verratti, Müller, Dybala — exact match | ✅ Perfect (scored 1.0 precision) |
| "best left-footed defenders" | Robertson, Alaba, Laporte, Jordi Alba — real, correctly left-footed defenders, but sorted by **overall rating**; ground truth ranks by **defending stat** specifically | ⚠️ Close, wrong stat chosen |
| "fast young strikers" | Mbappé, D. James, etc. — sorted by pace only; "young" (unstated age threshold) not applied | ❌ Unsolved — combines a sortable quality with a non-sortable one; current design only handles one `sort_by` field |
| "Messi vs Ronaldo" | Multiple Ronaldos, no Messi in data | ❌ Unrelated — entity name ambiguity, not a retrieval design issue |

**Honest read:** 2 of 5 questions now retrieve perfectly (up from 0 of 5 before
today's fix) — a real, verified improvement. 1 more is a near-miss caused by
genuine ambiguity in "best defenders" (which stat does "best" mean, absent a
named one?). The remaining 2 are known, separate limitations. The raw
aggregate RAGAS score does not reflect this improvement well, due to judge
infrastructure failures this run.

### 6.5 Open items (updated)

1. **Compound superlative + unstated-threshold queries** ("fast young
   strikers") — current `sort_by` design only handles a single ranking field;
   does not combine with implicit secondary qualifiers. Not yet solved.
2. **Ambiguous "best" without a named stat** — e.g. "best defenders" defaults
   to `overall`, but may reasonably mean the position-relevant stat
   (`defending` for CB/LB). Worth deciding whether to bias `sort_by` toward a
   position-appropriate stat when the question doesn't name one explicitly.
3. **Judge-model infra reliability** — two eval runs in a row have lost a
   meaningful fraction of judge-scoring jobs to Groq free-tier rate/token
   limits (5/20, then 8/20). Aggregate RAGAS numbers should be treated as
   directional, cross-checked manually against ground truth, not fully
   trusted at face value until this is addressed (e.g. lighter judge model,
   paid tier, or smaller batches with more retries).
4. Entity disambiguation ("which Ronaldo") — unrelated to retrieval strategy,
   separate future problem.
5. Branch/PR strategy — still undecided (see §5, carried over).