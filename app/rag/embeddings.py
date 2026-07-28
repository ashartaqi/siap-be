from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session, joinedload
from app.models import Player, DocumentEmbedding
from app.rag.text_builders import build_player_text

_model = None

def get_model() -> SentenceTransformer:
    """Lazy-load the model once per process."""
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_text(text: str) -> list[float]:
    model = get_model()
    return model.encode(text, normalize_embeddings=True).tolist()


def ingest_players(db: Session) -> int:
    """
    Builds embeddings for every player and writes them into document_embeddings.
    Deletes existing player embeddings first (simple full-refresh strategy for Phase 1).
    Returns the number of rows inserted.
    """
    players = (
        db.query(Player)
        .options(
            joinedload(Player.club),
            joinedload(Player.player_stats),
            joinedload(Player.goalkeeper_stats),
            joinedload(Player.positions),
        )
        .all()
    )

    # Full refresh: clear old player embeddings before regenerating
    db.query(DocumentEmbedding).filter(
        DocumentEmbedding.source_type == "player"
    ).delete()

    count = 0
    for player in players:
        text = build_player_text(player)
        vector = embed_text(text)

        row = DocumentEmbedding(
            source_type="player",
            source_id=player.id,
            content=text,
            embedding=vector,
        )
        db.add(row)
        count += 1

    db.commit()
    return count