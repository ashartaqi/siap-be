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
2. ~~Ambiguous "best" without a named stat~~ — **Resolved.** Updated the
   SORT INTENT prompt section to prefer a role-appropriate stat over
   `overall` when the question implies one through role/position (e.g.
   "best defenders" -> `defending`, "fastest players" -> `pace`), only
   falling back to `overall` for genuinely general questions ("best players
   overall"). Verified: "Who are the best left-footed defenders?" now
   extracts `sort_by: defending` (previously `overall`) and the full
   pipeline returns an exact match to ground truth (Bastoni, Laporte, Alaba,
   Chiellini, Acerbi — same 5 names and defending values, tie order among
   the 86s not deterministic). Note: the extractor now also returns a wider
   position set (`CB, LB, RB, CDM`) for "defenders" than the original eval's
   ground truth assumed (`CB, LB`) — a reasonable broadening, and confirmed
   not to change this particular result, but worth being aware of if other
   "defender" questions score differently than expected in future evals.
3. **Judge-model infra reliability** — two eval runs in a row have lost a
   meaningful fraction of judge-scoring jobs to Groq free-tier rate/token
   limits (5/20, then 8/20). Aggregate RAGAS numbers should be treated as
   directional, cross-checked manually against ground truth, not fully
   trusted at face value until this is addressed (e.g. lighter judge model,
   paid tier, or smaller batches with more retries).
4. Entity disambiguation ("which Ronaldo") — unrelated to retrieval strategy,
   separate future problem.
5. Branch/PR strategy — still undecided (see §5, carried over).

## 7. Aggregation Layer (Count / Average / Group-By Queries)

### 7.1 Motivation

Neither hard-constraint filtering nor sort-intent detection can answer
questions requiring a computed summary across many players — "how many
left-footed strikers are there," "which league has the highest average
defending rating." These require SQL aggregation (COUNT/AVG/GROUP BY), not
retrieval of any set of individual player documents, however well-ranked.
Attempting to answer these via document retrieval risks the LLM fabricating
a plausible-sounding but ungrounded number from a handful of retrieved rows.

### 7.2 Design

Extended `constraint_extractor.py` with an `aggregation` field
(`type`: count/avg/max/min/sum, `field`: the stat column, `group_by`: an
optional grouping dimension). Added `player_aggregations.py`, executing a
direct SQLAlchemy aggregate query and returning real computed numbers — no
LLM involved in the computation itself. `service.py` checks aggregation
intent first (reusing the single `extract_constraints()` call already made
for retrieval, avoiding a duplicate Gemini call); if present, routes to
`run_aggregation()` and formats the result as plain-text context for
`generate_answer()`, preserving the "answer only from provided context"
discipline for aggregated numbers too.

### 7.3 Bugs found and fixed during verification

Following the same call-per-step discipline as sort-by (§6), three distinct
bugs were found and fixed, each on a different code path's first real test:

1. **Filter bypass (count queries).** `run_aggregation()` initially never
   applied position/foot/age constraints to the count path — a count query
   for "left-footed strikers" returned 31,265 (the entire player table)
   instead of the correct 784. Root cause: the function never called the
   existing `_apply_shared_filters()` helper already used by the filter and
   sort paths. Fixed by reusing that helper directly rather than
   duplicating filter logic.
2. **GROUP BY column mismatch (grouped queries).** Selecting both
   `Club.name` and `Club.league_name` while grouping only by
   `Club.league_name` violates SQL's GROUP BY rules (every non-aggregated
   SELECT column must appear in GROUP BY). Fixed by selecting only the
   columns relevant to each specific grouping level.
3. **Missing query anchor (ungrouped stat queries).** A bare aggregate
   expression with no `group_by` (e.g. `MAX(pace)`) gave SQLAlchemy no
   entity to join `PlayerStats` from, raising
   `InvalidRequestError: Don't know how to join`. Fixed with an explicit
   `.select_from(Player)` anchor for the ungrouped case.

### 7.4 Verification (against direct-SQL ground truth, same method as Phase 2)

| Question | Ground truth (direct SQL) | Ask SIAP result | Match |
|---|---|---|---|
| "How many left-footed strikers are there?" | 784 | 784 | ✅ Exact |
| "Which league has the highest average defending rating?" | Premier League 57.81, Serie A 57.67, La Liga 56.90, Bundesliga 56.29, Russian Premier League 56.06 | Same 5 leagues, same values, same order | ✅ Exact |
| "What is the highest pace in the database?" | 97 | 97 | ✅ Exact |

All three distinct aggregation code paths (plain count, grouped average,
ungrouped max) are now verified correct, not just "runs without error."

### 7.5 Infrastructure note (unrelated to aggregation logic itself)

Testing this session repeatedly hit transient `503 UNAVAILABLE` ("model
experiencing high demand") errors from `gemini-flash-latest`. Confirmed this
is a Google-side, account-independent issue, not a bug in the pipeline.
`constraint_extractor.py`'s existing fail-open design handled this
correctly (falls back to `{}`, logs a warning) — but this exposed a real,
separate gap: when extraction fails and constraints come back empty, the
pipeline falls through to pure vector search even for clearly
aggregation-style questions, which can produce a fluent but completely
wrong answer (e.g. "72" instead of failing loudly, when the real answer was
97) with no visible indication to the user that retrieval silently
degraded. Additionally, `generation.py` has no error handling at all — a
`503` there crashes the request outright. Both are logged as open items
below, not yet fixed.

Separately: `gemini-2.5-flash` (used throughout this project until now)
began returning account-wide 404s as "no longer available," matching a
publicly reported Google-side issue rather than anything specific to this
project. Migrated both `constraint_extractor.py` and `generation.py` to
`gemini-flash-latest`, an alias Google maintains to track their current
recommended Flash model — chosen specifically to reduce exposure to future
model-deprecation churn.

### 7.6 Open items (carried over + new)

1. Compound superlative + unstated-threshold queries (§6.5, still open).
2. Judge-model (Groq) infra reliability for RAGAS evals (§6.5, still open).
3. Entity disambiguation ("which Ronaldo") — still open, unrelated to
   retrieval/aggregation design.
4. **New: silent degradation on extraction failure.** When
   `extract_constraints()` fails (rate limit, 503, etc.), aggregation and
   hybrid-filter intent are both lost, and the question falls through to
   pure vector search with no signal to the caller that this happened.
   Worth considering a distinguishable "low confidence" flag in the
   response when this occurs, rather than degrading silently.
5. ~~generation.py has no error handling~~ — **Resolved.** Added a
   try/except with logging around the generate_content call; verified via
   simulated failure (zero API cost): logs the real error and returns a
   graceful fallback message instead of crashing the request.
6. Multi-position double-counting (count queries) -- .distinct() fix applied
   in code, but NOT yet empirically verified. Attempted test ("How many
   midfielders playing CM or CDM are there?") did not exercise the intended
   path -- constraints did not resolve to aggregation intent (or extraction
   itself failed silently to a 503, indistinguishable from this output alone),
   and the question fell through to filtered retrieval instead. Still an
   open item: confirm extraction correctly detects count-intent for
   multi-position phrasing, then verify the distinct() fix against the
   7222 ground truth for CM/CDM.
7. Branch/PR strategy — still undecided (carried over from §5).


### 7.7 Truncated function bug (found post-commit) and final verification

After committing §7's work, a fourth aggregation shape (ungrouped `avg`) was
tested and returned a bare `None` instead of a result dict. Root cause:
`run_aggregation()`'s final `return` block (the `if group_by: ... else: ...`
dict construction) had been dropped during a prior file save — the function
fell straight through into `format_aggregation_context()`'s definition with
no `return` statement for the non-grouped case, so Python implicitly
returned `None`. This is the third instance of a partial/truncated file
save in this project (previously: a missing `format_aggregation_context`
function entirely, and a missing SORT INTENT section edit) — worth treating
as a process risk going forward, not just a one-off typo. Recommend a full
`cat`/`sed -n` review of any edited file immediately after saving, before
testing against it.

Fixed by restoring the missing return block. Verified for free (no API
calls) two ways: directly via `run_aggregation()` with hand-built
constraints, and independently via a raw SQLAlchemy query bypassing the
aggregation module entirely. Both returned 64.0336798336798337, matching
exactly.

**All four aggregation shapes now verified against ground truth:**

| Shape | Question / constraints | Ground truth | Result | Match |
|---|---|---|---|---|
| count (filtered) | Left-footed strikers | 784 | 784 | ✅ |
| avg, grouped | Avg defending by league | Premier League 57.81 (+ 4 more, exact order) | Same | ✅ |
| max, ungrouped | Highest pace | 97 | 97 | ✅ |
| avg, ungrouped | Avg overall rating (all players) | 64.0336798336798337 | Same | ✅ |

Aggregation layer considered feature-complete and verified as of this
entry.

### 7.8 Club-name filtering

**Motivation:** No way to filter or aggregate by club existed — surfaced by
testing "average overall rating at Real Madrid," which the extractor had
nowhere to route (no `club` field in the schema).

**Design:** Added `club` to the extraction prompt/schema (exact name as
stated, no guessing). Added a `Club` join + `ilike` filter to
`_apply_shared_filters()`, so club filtering is automatically available
across all three paths (hard-filter retrieval, sort-by ranking, and
aggregation) with no per-path duplication.

**Verification (ground truth via direct SQL, `AVG(p.overall)` for Real
Madrid — note: required qualifying `p.overall` explicitly, since `Club`
also has its own `overall` column, causing an ambiguous-column SQL error
on the first attempt):**

| Step | Result | Match |
|---|---|---|
| Ground truth (SQL) | 75.6486486486486486 | — |
| `run_aggregation()` direct (bypassing extractor) | 75.6486486486486486 | ✅ Exact |
| Full pipeline via `extract_constraints()` | Correctly extracted `club: 'Real Madrid'` | ✅ |

Club filtering considered verified and complete.

### 7.9 Compound superlative queries — transparency fix (not a full solve)

**Problem (from §6.5, item 1):** questions combining a sortable quality with
an unquantified one ("fast young strikers") had no good handling —
sort_by only supports one field, so unstated qualifiers like "young" were
silently dropped, or the model claimed "not enough information" outright
(see original Phase 2 eval, question 0).

**Design decision:** deliberately avoided building an automatic
multi-field weighted ranking (e.g. combining pace + age into one score) —
this would require an arbitrary weighting formula


### 7.10 Entity disambiguation

**Problem (§6.5, item 3 / original Phase 2 finding):** "Compare Messi and
Ronaldo" previously either found no exact match and gave up, or matched
wrong/multiple "Ronaldo"s without any resolution mechanism.

**Design:** Added `player_names` extraction to `constraint_extractor.py`.
New `find_player_name_matches()` in `player_filters.py` looks up players by
`short_name` (deliberately not `long_name` — see bug below), ordered by
`overall` descending so the most relevant/famous matches surface first.
`service.py` checks name matches before any other retrieval path: zero
matches -> tell the user the name wasn't found; multiple matches -> list
real candidates with distinguishing info (nationality, club) and ask the
user to clarify, rather than guessing.

**Bug found during free verification:** initial version matched against
`long_name` too (`OR long_name ILIKE ...`), which matched "Ronaldo" against
many unrelated players who simply have "Ronaldo" as a middle/given name
(e.g. "Ronaldo Jailson Cabrais Petri", commonly known as "Ronaldo
Cabrais") —10+ false-positive matches, none of which included the actual
well-known Ronaldos from the original eval. Fixed by matching `short_name`
only (the commonly-used name) and ordering by `overall` descending.

**Verified (real pipeline call, after two prior attempts were interrupted
by transient 503s):** "Compare Messi and Ronaldo dribbling and passing"
now correctly identifies real matches for both names (Lionel Messi at
PSG; Cristiano Ronaldo at Al Nassr, listed first among 7 Ronaldo
candidates) and asks the user to clarify which player they mean, instead
of silently guessing or comparing the wrong players. Also correctly
noted that dribbling/passing data wasn't available in the
disambiguation-only context, rather than fabricating a comparison.

Item 3 in §6.5 considered resolved.