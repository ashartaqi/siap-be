from sqlalchemy.orm import Session
from app.models import DocumentEmbedding
from app.rag.embeddings import embed_text
from app.rag.constraint_extractor import extract_constraints
from app.rag.player_filters import build_filtered_player_ids


def retrieve_relevant_players(db: Session, query: str, top_k: int = 5) -> list[DocumentEmbedding]:
    query_vector = embed_text(query)
    constraints = extract_constraints(query)
    player_ids = build_filtered_player_ids(db, constraints)

    embedding_query = db.query(DocumentEmbedding).filter(DocumentEmbedding.source_type == "player")

    if player_ids is not None:
        if not player_ids:
            return []  # constraints matched nothing — honest empty result, not a fallback
        embedding_query = embedding_query.filter(DocumentEmbedding.source_id.in_(player_ids))

    return (
        embedding_query
        .order_by(DocumentEmbedding.embedding.cosine_distance(query_vector))
        .limit(top_k)
        .all()
    )