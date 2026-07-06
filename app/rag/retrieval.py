from sqlalchemy.orm import Session
from app.models import DocumentEmbedding
from app.rag.embeddings import embed_text


def retrieve_relevant_players(db: Session, query: str, top_k: int = 5) -> list[DocumentEmbedding]:
    query_vector = embed_text(query)

    results = (
        db.query(DocumentEmbedding)
        .filter(DocumentEmbedding.source_type == "player")
        .order_by(DocumentEmbedding.embedding.cosine_distance(query_vector))
        .limit(top_k)
        .all()
    )
    return results