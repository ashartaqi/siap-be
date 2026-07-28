from sqlalchemy.orm import Session
from app.rag.constraint_extractor import extract_constraints
from app.rag.retrieval import retrieve_relevant_players
from app.rag.player_aggregations import run_aggregation, format_aggregation_context
from app.rag.generation import generate_answer


def ask_siap(db: Session, question: str) -> dict:
    constraints = extract_constraints(question)

    agg_result = run_aggregation(db, constraints)
    if agg_result is not None:
        context = format_aggregation_context(agg_result)
        answer = generate_answer(question, [context])
        return {
            "answer": answer,
            "sources": [context],
        }

    results = retrieve_relevant_players(db, question, constraints, top_k=5)
    contexts = [r.content for r in results]

    answer = generate_answer(question, contexts)

    return {
        "answer": answer,
        "sources": contexts,
    }