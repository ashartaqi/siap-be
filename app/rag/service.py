from sqlalchemy.orm import Session
from app.rag.constraint_extractor import extract_constraints
from app.rag.retrieval import retrieve_relevant_players
from app.rag.player_filters import find_player_name_matches
from app.rag.player_aggregations import run_aggregation, format_aggregation_context
from app.rag.generation import generate_answer
from app.rag.extraction_heuristic import needs_constraint_extraction, _get_known_club_names
from app.models import DocumentEmbedding

_known_club_names_cache: set[str] | None = None


def _get_cached_club_names(db: Session) -> set[str]:
    global _known_club_names_cache
    if _known_club_names_cache is None:
        _known_club_names_cache = _get_known_club_names(db)
    return _known_club_names_cache


def ask_siap(db: Session, question: str) -> dict:
    club_names = _get_cached_club_names(db)

    if needs_constraint_extraction(question, known_club_names=club_names):
        constraints = extract_constraints(question)
    else:
        constraints = {}

    extraction_failed = constraints.pop("_extraction_failed", False)
    unquantified = constraints.get("unquantified_qualifiers")

    degraded_note = None
    if extraction_failed:
        degraded_note = (
            "Note: constraint extraction was temporarily unavailable for this question, "
            "so results below are from a broader search and may be less precise than usual."
        )

    player_names = constraints.get("player_names")
    if player_names:
        ambiguous_or_missing = []
        resolved_ids = []

        for name in player_names:
            matches = find_player_name_matches(db, name)
            if len(matches) == 0:
                ambiguous_or_missing.append(f'No player named "{name}" was found in the database.')
            elif len(matches) > 1:
                candidates = "; ".join(
                    f"{p.long_name} ({p.short_name}, {p.nationality_name}, plays for {p.club_name or 'no club'})"
                    for p in matches
                )
                ambiguous_or_missing.append(f'Multiple players match "{name}": {candidates}. Ask the user which one they mean.')
            else:
                resolved_ids.append(matches[0].id)

        if ambiguous_or_missing:
            contexts = ambiguous_or_missing
            if degraded_note:
                contexts = [degraded_note] + contexts
            answer = generate_answer(question, contexts, unquantified)
            return {"answer": answer, "sources": contexts, "degraded": extraction_failed}

        if resolved_ids:
            docs = (
                db.query(DocumentEmbedding)
                .filter(
                    DocumentEmbedding.source_type == "player",
                    DocumentEmbedding.source_id.in_(resolved_ids),
                )
                .all()
            )
            contexts = [d.content for d in docs]
            if degraded_note:
                contexts = [degraded_note] + contexts
            answer = generate_answer(question, contexts, unquantified)
            return {"answer": answer, "sources": contexts, "degraded": extraction_failed}

    agg_result = run_aggregation(db, constraints)
    if agg_result is not None:
        contexts = [format_aggregation_context(agg_result)]
        if degraded_note:
            contexts = [degraded_note] + contexts
        answer = generate_answer(question, contexts, unquantified)
        return {"answer": answer, "sources": contexts, "degraded": extraction_failed}

    contexts = retrieve_relevant_players(db, question, constraints, top_k=5)
    contexts = [r.content for r in contexts]
    if degraded_note:
        contexts = [degraded_note] + contexts

    answer = generate_answer(question, contexts, unquantified)
    return {"answer": answer, "sources": contexts, "degraded": extraction_failed}