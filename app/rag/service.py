from sqlalchemy.orm import Session
from app.rag.constraint_extractor import extract_constraints
from app.rag.retrieval import retrieve_relevant_players
from app.rag.player_filters import find_player_name_matches
from app.rag.player_aggregations import run_aggregation, format_aggregation_context
from app.rag.generation import generate_answer
from app.rag.extraction_heuristic import needs_constraint_extraction, get_known_club_names
from app.models import DocumentEmbedding

_known_club_names_cache: set[str] | None = None


def _get_cached_club_names(db: Session) -> set[str]:
    global _known_club_names_cache
    if _known_club_names_cache is None:
        _known_club_names_cache = get_known_club_names(db)
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
        missing_notes = []
        disambiguation_notes = []
        resolved_ids = []

        for name in player_names:
            matches = find_player_name_matches(db, name)
            if len(matches) == 0:
                missing_notes.append(f'No player named "{name}" was found in the database.')
            elif len(matches) == 1:
                resolved_ids.append(matches[0].id)
            else:
                top = matches[0]
                resolved_ids.append(top.id)
                alternates = "; ".join(f"{p.long_name} ({p.short_name})" for p in matches[1:5])
                disambiguation_notes.append(
                    f'"{name}" matched multiple players; assumed {top.long_name} ({top.short_name}), '
                    f'the highest-rated match (other possibilities: {alternates}).'
                )

        if missing_notes and not resolved_ids:
            contexts = missing_notes
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
            contexts = missing_notes + contexts
            if degraded_note:
                contexts = [degraded_note] + contexts
            answer = generate_answer(question, contexts, unquantified, disambiguation_notes)
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