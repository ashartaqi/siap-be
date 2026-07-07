# Ask SIAP — Phase 2 Findings: RAGAS Evaluation

**Date:** July 2026
**Author:** Nafay
**Scope:** Evaluation of the Phase 1 pgvector retrieval baseline using RAGAS metrics, judged by Groq (`llama-3.3-70b-versatile`), against Gemini 2.5 Flash as the generation model.

---

## 1. Objective

Phase 1 established a working end-to-end RAG pipeline for Ask SIAP: pgvector-backed embeddings over ~31,000 players, semantic retrieval via cosine distance, and Gemini-based answer generation through a live `/ask` endpoint.

Manual spot-checks during Phase 1 suggested retrieval was inconsistent — surfacing irrelevant players (e.g., a 48-year-old goalkeeper for a "young fast strikers" query). Phase 2's goal was to replace that anecdotal impression with a measured, reproducible evaluation using RAGAS.

## 2. Method

- **Eval set:** 5 hand-picked questions targeting different structured query types (age + position + pace, goalkeeper stat ranking, name comparison, foot + position + stat ranking, position + rating ranking).
- **Ground truths:** Derived directly from the database via targeted SQLAlchemy queries (`eval_helpers.py`), not guessed — each ground truth reflects the actual top matches in the 31k-player dataset.
- **Generation model:** Gemini 2.5 Flash (`google-genai` SDK).
- **Judge model:** Groq `llama-3.3-70b-versatile`, temperature 0, via `langchain-groq`, deliberately chosen to be a different model family from the generator to avoid self-judging bias.
- **Metrics:** context precision, context recall, faithfulness, answer relevancy (RAGAS 0.1.21).

## 3. Results

| Question | Context Precision | Context Recall | Faithfulness | Answer Relevancy |
|---|---|---|---|---|
| Fast young strikers | — | 0.0 | 1.00 | 0.79 |
| Best goalkeeper reflexes | — | 0.0 | 1.00 | 0.68 |
| Messi vs Ronaldo comparison | — | — | — | — |
| Best left-footed defenders | 0.0 | 0.0 | 0.75 | 0.79 |
| Best attacking midfielders | 0.0 | — | — | — |

*Some cells are blank due to Groq free-tier rate limiting (daily token cap reached mid-run), not evaluation failure. Every cell that did compute for context precision and context recall returned exactly 0.0 — no partial or borderline scores.*

**Aggregate (partial, from completed judgments):**
- Context Precision: **0.0**
- Context Recall: **0.0**
- Faithfulness: **~0.92**
- Answer Relevancy: **~0.75**

## 4. Interpretation

**Generation is reliable.** Faithfulness scores near 1.0 across every question that computed, meaning Gemini consistently answered only from the context it was given and explicitly said so when the data was insufficient (e.g., "no player named Messi in the provided data" rather than fabricating stats). Answer relevancy in the 0.68–0.79 range indicates responses stayed on-topic even when the underlying context was poor.

**Retrieval is not working for structured queries.** Both context precision and context recall measured exactly 0.0 wherever they computed — not a low score, a complete absence of relevant players in the top-5 retrieved results. This means the correct players (e.g., real strikers under 25, actual goalkeepers, genuine left-footed defenders) were not merely ranked below irrelevant ones — they were not present in the retrieved set at all.

This points to a specific root cause: `all-MiniLM-L6-v2` sentence embeddings capture loose topical/semantic similarity well, but do not reliably encode precise categorical and numeric constraints (age thresholds, exact position codes, preferred foot, stat thresholds) embedded as plain text. This is a structural limitation of pure semantic search on structured data, not a tuning problem — a larger or different embedding model would likely help only marginally, since the underlying issue is architectural, not a matter of embedding quality.

## 5. Recommended Fix: Hybrid Retrieval

Rather than relying solely on cosine similarity across all embeddings, the recommended approach is a **hybrid SQL + vector retrieval pipeline**:

1. Extract structured constraints from the user's question (position, age range, preferred foot, stat thresholds) — either via lightweight parsing or an LLM-based query interpreter.
2. Apply these as hard SQL filters against `players`/`player_stats` first, narrowing the candidate pool.
3. Use vector similarity only to rank *within* that filtered set for fuzzier qualities ("promising," "well-rounded," etc.) that don't map to a single column.

This is a standard, well-established pattern for RAG over structured/tabular data, and directly addresses the recall=0.0 finding — since SQL filtering guarantees relevant rows are present in the candidate set before any ranking occurs.

## 6. Status and Next Steps

- Phase 1 (pgvector baseline, ingestion, `/ask` endpoint): **complete and functional**
- Phase 2 (RAGAS evaluation): **complete for this eval set**; further runs deferred due to Groq free-tier daily rate limits
- Immediate next step: design and implement hybrid SQL+vector retrieval as a Phase 2.5 addition before proceeding to Phase 3 (RAPTOR clustering), since RAPTOR will inherit and compound any retrieval weakness present in the current baseline
- Eval set should be expanded beyond 5 questions once hybrid retrieval is in place, to confirm the fix generalizes

## 7. Appendix: Known Limitations of This Evaluation

- Small eval set (n=5) — sufficient to detect a strong, consistent failure pattern (0.0 precision/recall), but not enough for fine-grained comparison between retrieval strategies later.
- Groq free-tier rate limits prevented a fully complete run; the pattern found (0.0 on precision/recall) was consistent across every row that did complete, which is treated as sufficient evidence given the uniformity of the result.
- Player dataset is a static snapshot (FIFA/EA FC-style historical data), not live current-season stats — relevant context if these findings or the demo are shared externally.
