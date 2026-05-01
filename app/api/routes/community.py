from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.models import User
from app.core.security import get_current_user
from app.schemas import ChatMessage, ChatMessageCreate

router = APIRouter()

@router.get("", response_model=list[ChatMessage])
def get_chat_messages(db: Session = Depends(get_db), current_user: User = Depends(get_current_user), limit: int = 50):
    try:
        messages = crud.get_chat_messages(db, limit)
        return messages
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("", response_model=ChatMessage, status_code=status.HTTP_201_CREATED)
def send_chat_message(payload: ChatMessageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        message = crud.create_chat_message(db, user_id=current_user.id, content=payload.content)
        return {
            "id": message.id,
            "user_id": message.user_id,
            "username": current_user.username,
            "content": message.content,
            "created_at": message.created_at
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
