from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.models import User
from app.core.security import get_current_user
from app.schemas import ChatMessageRead, ChatMessageCreate

router = APIRouter()


@router.get("", response_model=list[ChatMessageRead])
def get_chat_messages(db: Session = Depends(get_db), current_user: User = Depends(get_current_user), limit: int = 50):
    chat_msg = crud.get_chat_messages(db, limit)
    return chat_msg


@router.post("", response_model=ChatMessageRead, status_code=status.HTTP_201_CREATED)
def send_chat_message(payload: ChatMessageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    message, reward = crud.create_chat_message(db, user_id=current_user.id, content=payload.content)
    resp = ChatMessageRead.model_validate(message)
    resp.reward_amount = reward if reward > 0 else None
    return resp
