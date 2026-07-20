from sqlalchemy.orm import Session
from app.rag.constraint_extractor import extract_constraints
from app.rag.retrieval import retrieve_relevant_players
from app.rag.player_filters import find_player_name_matches
from app.rag.player_aggregations import run_aggregation, format_aggregation_context
from app.rag.generation import generate_answer
from app.models import DocumentEmbedding


def ask_siap(db: Session, question: str) -> dict:
    constraints = extract_constraints(question)
    unquantified = constraints.get("unquantified_qualifiers")

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
            context = "\n".join(ambiguous_or_missing)
            answer = generate_answer(question, [context], unquantified)
            return {"answer": answer, "sources": [context]}

        if resolved_ids:
            # All names resolved to exactly one match each -- fetch them
            # directly by ID rather than relying on vector search, which
            # isn't guaranteed to surface every named player.
            docs = (
                db.query(DocumentEmbedding)
                .filter(
                    DocumentEmbedding.source_type == "player",
                    DocumentEmbedding.source_id.in_(resolved_ids),
                )
                .all()
            )
            contexts = [d.content for d in docs]
            answer = generate_answer(question, contexts, unquantified)
            return {"answer": answer, "sources": contexts}

    agg_result = run_aggregation(db, constraints)
    if agg_result is not None:
        context = format_aggregation_context(agg_result)
        answer = generate_answer(question, [context], unquantified)
        return {
            "answer": answer,
            "sources": [context],
        }

    results = retrieve_relevant_players(db, question, constraints, top_k=5)
    contexts = [r.content for r in results]

    answer = generate_answer(question, contexts, unquantified)

    return {
        "answer": answer,
        "sources": contexts,
    }