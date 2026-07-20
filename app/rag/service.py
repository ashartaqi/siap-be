from sqlalchemy.orm import Session
from app.rag.constraint_extractor import extract_constraints
from app.rag.retrieval import retrieve_relevant_players
from app.rag.player_filters import find_player_name_matches
from app.rag.player_aggregations import run_aggregation, format_aggregation_context
from app.rag.generation import generate_answer


def ask_siap(db: Session, question: str) -> dict:
    constraints = extract_constraints(question)
    unquantified = constraints.get("unquantified_qualifiers")

    player_names = constraints.get("player_names")
    if player_names:
        name_status = []
        for name in player_names:
            matches = find_player_name_matches(db, name)
            if len(matches) == 0:
                name_status.append(f'No player named "{name}" was found in the database.')
            elif len(matches) > 1:
                candidates = "; ".join(
                    f"{p.long_name} ({p.short_name}, {p.nationality_name}, plays for {p.club_name or 'no club'})"
                    for p in matches
                )
                name_status.append(f'Multiple players match "{name}": {candidates}. Ask the user which one they mean.')
        if name_status:
            context = "\n".join(name_status)
            answer = generate_answer(question, [context], unquantified)
            return {"answer": answer, "sources": [context]}

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