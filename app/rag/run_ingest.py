# app/rag/run_ingest.py
from app.core.db import SessionLocal
from app.rag.embeddings import ingest_players

if __name__ == "__main__":
    db = SessionLocal()
    try:
        count = ingest_players(db)
        print(f"Embedded {count} players into document_embeddings.")
    finally:
        db.close()