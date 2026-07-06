from sqlalchemy.orm import Session
from app.rag.retrieval import retrieve_relevant_players
from app.rag.generation import generate_answer


def ask_siap(db: Session, question: str) -> dict:
    results = retrieve_relevant_players(db, question, top_k=5)
    contexts = [r.content for r in results]

    answer = generate_answer(question, contexts)

    return {
        "answer": answer,
        "sources": contexts,
    }