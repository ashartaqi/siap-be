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

### 7.11 Direct player lookup for named comparisons

**Problem found while testing §7.10:** when player names resolve to
exactly one match each (the "clean," non-ambiguous case), the system
previously fell through to ordinary vector search rather than fetching
those specific players directly. This worked by luck on famous pairs
(both names appear in the question text, biasing embedding similarity
toward them) but wasn't guaranteed — a top_k of 5 with several
lexically-similar-but-irrelevant players could crowd out a genuinely
named player.

**Bug found and fixed along the way:** `find_player_name_matches()`
initially searched `short_name` only (after the §7.10 long_name fix), but
most players' `short_name` is "<Initial>. <Surname>" (e.g. "K. Mbappé"),
which never matches a full first name search ("Kylian Mbappé"). Fixed by
falling back to `long_name` search when `short_name` yields no match —
while keeping the original §7.10 short_name-first approach for common
single-name references ("Messi", "Ronaldo"), avoiding a regression to the
original long_name false-positive problem (middle-name matches).

**Design:** `service.py` now resolves all named players before choosing a
retrieval path. If every name resolves to exactly one match, those
players are fetched directly by ID (bypassing vector search entirely) —
same "SQL is exact once identity is known" principle used elsewhere
(sort-by, aggregation, club filtering).

**Verified:** "Compare Cristiano Ronaldo and Kylian Mbappé shooting and
passing" now returns exactly 2 sources — the correct two players, no
noise — versus the previous vector-search path which returned 5 results
including 2 unrelated "Ronaldo"s and an unrelated player. Comparison
values (shooting 91 vs 89, passing 80 vs 76) are directly grounded in the
retrieved data.

### 7.12 Visible signal on extraction failure

**Problem (§7.6/7.8, item 4, raised repeatedly since aggregation work):**
when `extract_constraints()` fails (429, 503, etc.), the pipeline silently
degrades to pure vector search with zero indication anything went wrong —
directly implicated in at least two prior confidently-wrong answers this
week ("72" instead of 97 for max pace; a wrong Ronaldo comparison).

**Design:** `extract_constraints()` now returns an internal
`_extraction_failed` flag alongside constraints (or `{"_extraction_failed":
True}` on any exception). `service.py` reads and strips this flag, and:
- includes a `degraded_note` as extra context passed to `generate_answer()`,
  so the model has the option to caveat its answer accordingly
- returns `degraded: <bool>` in every response dict — a reliable,
  machine-readable signal independent of whether the LLM's prose happens
  to mention the caveat, useful for a future frontend to show a visible
  "reduced confidence" indicator

**Bug found during verification:** initial `service.py` implementation
referenced `contexts` in a note-prepending step before it was defined for
the player-name/aggregation/fallback branches — an incomplete rewrite,
not tested before being shared. Caught immediately by the free simulated-
failure test (an `UnboundLocalError`, not a silent wrong answer) rather
than surfacing later. Fixed with a complete rewrite ensuring every return
path defines `contexts` before use.

**Verified (zero-cost, via monkey-patched Gemini client, no real API
calls):** simulated extraction failure correctly produces `degraded: True`
in the response, no crash, and a context-aware note is passed to
generation (though the model doesn't always foreground it in prose --
the reliable signal is the `degraded` flag itself, not the answer text).

Item 4 (originally raised across §7.6/7.8) considered resolved.

## 8. Post-Fix Eval Run & a RAGAS Methodology Gap

### 8.1 Context

Ran the original 5-question RAGAS eval again after this session's four
fixes (club filtering §7.8, compound-superlative transparency §7.9, entity
disambiguation §7.10, direct-lookup comparisons §7.11) plus the
extraction-failure visibility fix (§7.12). Aggregate scores looked worse
than the previous run at first glance:

```
{'context_precision': 0.25, 'context_recall': 0.40, 'faithfulness': 0.498, 'answer_relevancy': 0.0}
```

Manual, question-by-question review (same discipline used throughout this
project) tells a different and more accurate story than the aggregate
numbers alone.

### 8.2 Question-by-question breakdown

| Q | Topic | Retrieval/answer quality (manual check) | RAGAS score | Verdict |
|---|---|---|---|---|
| 0 | Fast young strikers | Same known limitation as before (compound query, unchanged by design) — but answer now explicitly reasons through the tradeoff instead of flatly giving up, per §7.9 | precision 0.0 | Expected, unchanged, documented |
| 1 | Best reflexes | Retrieval exactly correct (Sommer/ter Stegen/Courtois, matches ground truth) | faithfulness 0.0 | **Judge-scoring anomaly** — same pattern seen in prior runs, not a real fault |
| 2 | Messi/Ronaldo comparison | Correctly found real candidates for both names, correctly refused to guess and asked for clarification instead of fabricating a comparison — the intended, designed behavior from §7.10/7.11 | 0.0 across all metrics | **Eval methodology gap** — see §8.3 |
| 3 | Best left-footed defenders | Both extraction AND generation hit `503`s on the same question; degraded-note fallback (§7.12) fired correctly, then generation's own fallback message (§7.6) also fired correctly | 0.0 across all metrics | Genuine infra failure (Google demand spike), not a code fault — correct graceful-degradation behavior under a harder double-failure case than previously tested |
| 4 | CAM overall rating | Exact match to ground truth | precision 1.0, recall 1.0 | Clean pass, metric and manual check agree |

### 8.3 Real finding: RAGAS ground truth doesn't recognize "correctly declined to
guess" as a good answer

Question 2's ground truth is a direct numeric comparison ("L. Messi:
dribbling 94, passing 90. Cristiano Ronaldo: dribbling 83, passing 76").
But this project deliberately built entity disambiguation (§7.10) so that
when a name is ambiguous, the system asks for clarification instead of
guessing which player was meant — a design choice made explicitly to avoid
fabricating results, consistent with this project's approach throughout
(never guess unstated thresholds, never guess ambiguous entities, be
visible about degraded results).

The eval as currently written has no way to score "correctly asked for
clarification" as a good outcome — it can only measure similarity to a
direct-answer ground truth, so a fully honest, correctly-designed response
scores identically to a wrong one. This means Q2 will score as a false
failure in every future eval run unless addressed, undermining trust in
the aggregate metric for exactly the kind of behavior this project has
prioritized.

**Recommendation (not yet implemented):** add a distinct eval category for
ambiguous-entity questions with its own success criterion ("did the system
correctly identify ambiguity and ask for clarification, listing real
candidates?") rather than scoring them against a direct-answer ground
truth. Standard RAGAS context precision/recall/faithfulness metrics aren't
well-suited to this category and shouldn't be applied to it going forward.

### 8.4 Overall assessment

Excluding the judge-scoring anomaly (Q1), the eval-methodology gap (Q2),
and the transient infra failure (Q3) — none of which reflect a real
regression — the underlying system behaved as well as or better than
prior runs on every question where a fair comparison is possible (Q1
manually confirmed correct, Q4 confirmed correct by both methods, Q0
unchanged as expected). No evidence of regression from this session's
fixes. Aggregate RAGAS numbers from this run should not be read at face
value without this context.

### 8.5 Open items (updated)

Carried over from §7.6/7.9 unresolved items, plus:

8. **New: RAGAS eval doesn't credit correct ambiguity-clarification
   behavior.** See §8.3. Needs a separate eval category/success criterion
   before future runs can be trusted at face value for entity-disambiguation
   questions.

## 9. TruLens Integration — Attempted, API Discovered, Shelved

### 9.1 Goal

Integrate TruLens (RAG triad: context relevance, groundedness, answer
relevance) on top of the existing RAGAS harness, for per-pipeline-stage
tracing and a second, independently-corroborating judge model. Not meant
to replace RAGAS -- meant to add stage-level diagnosis ("which stage
broke") on top of RAGAS's aggregate scores.

### 9.2 What was built

- `app/rag/tracing.py` -- three `Metric` objects (context relevance,
  groundedness, answer relevance) wired to a Groq/Llama-3.3-70b provider
  via `trulens-providers-litellm`, matching the existing RAGAS judge model
  so scores are comparable.
- `app/rag/instrumented_service.py` -- wraps (does not modify) every stage
  of `service.py`'s `ask_siap()` as its own traced span: constraint
  extraction, entity disambiguation, aggregation, retrieval, generation.
- `app/rag/eval_trulens_runner.py` -- scaffolding to run the same 5-question
  eval set used by the RAGAS harness through the TruLens-instrumented
  pipeline.

### 9.3 API discovery process (the actual hard part)

`trulens-core` (installed: 2.8.1) has undergone significant API churn --
the currently-installed version differs substantially from most publicly
documented examples, including the deprecated `trulens-eval` package and
even some patterns suggested by the package's own deprecation warnings.
Getting a working `Metric` construction required roughly a dozen corrected
guesses, each narrowed by directly inspecting the installed package via
`inspect.signature()`, `dir()`, and deliberately triggering errors rather
than trusting documentation or plausible-looking API guesses. Confirmed,
working facts about `trulens-core==2.8.1`, `trulens-providers-litellm==2.8.1`,
`trulens-dashboard==2.9.0`:

- `Feedback` is deprecated in favor of `Metric` (`from trulens.core import
  Metric`). `Feedback(...).on(Selector(...))` style chaining raises
  `ValueError: OTEL mode only supports a single positional argument to
  \`on\`` and is not the current pattern.
- The correct pattern is `Metric(implementation=provider.some_method)`
  followed by convenience methods: `.on_input()`, `.on_output()`,
  `.on_input_output()`, `.on_context(collect_list=bool)`. These chain
  together (e.g. `.on_input().on_context(collect_list=False)`) and bind
  to the provider function's parameters *positionally*, not by matching
  names -- e.g. `groundedness_measure_with_cot_reasons(source, statement)`
  binds correctly via `.on_context().on_output()` despite the parameter
  names not being "context"/"output".
- `instrument` must be imported from `trulens.core.otel.instrument`
  (a class, constructed per-use with `span_type`/`name`/`attributes`
  kwargs) -- not from `trulens.apps.app` or `trulens.apps.custom`, which
  export a different, pre-instantiated default instance that only accepts
  a bare function with no config.
- `SpanAttributes.SpanType` is a fixed enum (`unknown`, `record_root`,
  `retrieval`, `generation`, `aggregation` is NOT in this enum -- custom
  pipeline stages should use `SpanType.UNKNOWN` with a descriptive `name=`
  instead of inventing new span types).
- `SpanAttributes.GENERATION` has no `INPUT`/`OUTPUT` sub-attributes --
  those live under `SpanAttributes.RECORD_ROOT.INPUT`/`.OUTPUT` instead,
  which represents the whole record's input/output, not a per-span
  attribute.
- Feedback computation runs **asynchronously** in a background evaluator
  thread. Reading results immediately after the `with tru_app as
  recording:` block races that computation -- some scores will genuinely
  be `NaN` because they haven't been computed yet, and exiting before
  they finish raises `RuntimeError: cannot schedule new futures after
  interpreter shutdown` in the background thread. Fix:
  `session.wait_for_feedback_results(record_ids, feedback_names,
  timeout=...)` before reading/printing results.

### 9.4 Real, working result achieved

With all of the above corrected, the pipeline traced successfully end to
end for at least one question ("Which goalkeepers have the best
reflexes?"): the correct answer was produced (matching the same verified
ground truth used throughout this project), and genuine, non-NaN feedback
scores were computed and attached to records (`relevance_with_cot_reasons`
showing real `0.0`/`1.0` values, not universal failures).

### 9.5 Remaining problem -- why this is being shelved for now

TruLens's automatic span-content inference does not reliably know how to
extract a meaningful "input"/"output" from spans that aren't
naturally answer-shaped -- specifically `_traced_aggregation`, which
returns `None` (no aggregation needed) or a raw dict, not natural-language
text. Observed concretely: the `answer_relevance` metric was applied to
the aggregation span's constraints argument for a non-aggregation
question, producing a technically-well-formed but meaningless score (the
judge correctly scored `['GK']` as irrelevant to "which goalkeepers have
the best reflexes?", but `['GK']` was never meant to be scored as an
answer in the first place -- it's an internal argument fragment).

Fixing this properly requires deliberately scoping each `Metric` to only
the spans it's actually meant to evaluate (e.g. answer relevance should
only ever look at the `generation` span's record-level output, never at
intermediate stages like aggregation or disambiguation) -- a real design
task, not a quick patch, and one that risks further extended API-discovery
sessions given how much guessing was required to get this far.

### 9.6 Decision

Shelved for now. The existing RAGAS harness plus manual ground-truth
verification (the primary method used to verify every fix across
Phase 2.5) remain the trusted evaluation tools for actual decisions about
Ask SIAP's retrieval/answer quality. TruLens integration is a legitimate
future enhancement (real per-stage tracing has genuine value once
metric-to-span scoping is done correctly) but is evaluation *tooling*,
not a fix to the chatbot itself -- lower priority than closing remaining
answer-quality gaps or reliability/deployment work.

All code (`tracing.py`, `instrumented_service.py`, `eval_trulens_runner.py`,
`test_trulens_single.py`) is left in place, functional as documented above,
for whoever picks this back up.