from sqlalchemy.orm import Session
from app.models import DocumentEmbedding
from app.rag.embeddings import embed_text
from app.rag.constraint_extractor import extract_constraints
from app.rag.player_filters import build_filtered_player_ids, build_ranked_player_ids


def retrieve_relevant_players(db: Session, query: str, top_k: int = 5) -> list[DocumentEmbedding]:
    constraints = extract_constraints(query)

    # Ranking queries ("best reflexes") skip vector search entirely —
    # once you know the stat to sort by, there's no fuzziness left to rank.
    ranked_ids = build_ranked_player_ids(db, constraints, top_k=top_k)
    if ranked_ids is not None:
        if not ranked_ids:
            return []
        results = (
            db.query(DocumentEmbedding)
            .filter(
                DocumentEmbedding.source_type == "player",
                DocumentEmbedding.source_id.in_(ranked_ids),
            )
            .all()
        )
        # preserve the SQL ranking order, since the IN clause doesn't guarantee it
        order = {pid: i for i, pid in enumerate(ranked_ids)}
        return sorted(results, key=lambda r: order.get(r.source_id, len(order)))

    query_vector = embed_text(query)
    player_ids = build_filtered_player_ids(db, constraints)

    embedding_query = db.query(DocumentEmbedding).filter(DocumentEmbedding.source_type == "player")

    if player_ids is not None:
        if not player_ids:
            return []
        embedding_query = embedding_query.filter(DocumentEmbedding.source_id.in_(player_ids))

    return (
        embedding_query
        .order_by(DocumentEmbedding.embedding.cosine_distance(query_vector))
        .limit(top_k)
        .all()
    )