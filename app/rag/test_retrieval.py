# app/rag/test_retrieval.py
from app.core.db import SessionLocal
from app.rag.retrieval import retrieve_relevant_players

if __name__ == "__main__":
    db = SessionLocal()
    try:
        query = "fast young strikers with high dribbling"
        results = retrieve_relevant_players(db, query, top_k=5)
        for r in results:
            print(r.content)
            print("---")
    finally:
        db.close()