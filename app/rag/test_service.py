# app/rag/test_service.py
from app.core.db import SessionLocal
from app.rag.service import ask_siap

if __name__ == "__main__":
    db = SessionLocal()
    try:
        result = ask_siap(db, "Who are some fast young strikers?")
        print(result["answer"])
        print("\n--- Sources ---")
        for s in result["sources"]:
            print(s[:100], "...")
    finally:
        db.close()