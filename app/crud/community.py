from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from datetime import datetime, timezone
from app.models import ChatMessage, MatchComment, User
from app.constants import CHAT_REWARD, MATCH_COMMENT_REWARD
from app.crud.users import create, add_bb_reward

def get_chat_messages(db: Session, limit: int = 50):
    messages = (
        db.query(ChatMessage)
        .options(joinedload(ChatMessage.user))
        .order_by(desc(ChatMessage.created_at))
        .limit(limit)
        .all()
    )
    return list(reversed(messages))

def create_chat_message(db: Session, user_id: int, content: str):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    reward = 0
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        first_today = not db.query(ChatMessage).filter(
            ChatMessage.user_id == user_id,
            ChatMessage.created_at >= today_start,
        ).first()
        if first_today:
            reward = CHAT_REWARD
            user.bb_balance += reward
            db.flush()

    message = ChatMessage(user_id=user_id, content=content)
    db_message = create(db, message, "Error sending message")
    return db_message, reward

def get_match_comments(db: Session, match_id: int):
    return (
        db.query(MatchComment)
        .options(joinedload(MatchComment.user))
        .filter(MatchComment.match_id == match_id)
        .order_by(MatchComment.created_at.desc())
        .all()
    )

def create_match_comment(db: Session, user_id: int, match_id: int, content: str):
    comment = MatchComment(user_id=user_id, match_id=match_id, content=content)

    reward = MATCH_COMMENT_REWARD
    add_bb_reward(db, user_id, reward)

    db_comment = create(db, comment, "Error posting comment")
    return db_comment, reward
