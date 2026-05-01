from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.models import User
from app.core.security import get_current_user
from app.schemas import MatchCommentRead, MatchCommentCreate

router = APIRouter()


@router.get("/{match_id}", response_model=list[MatchCommentRead])
def get_match_comments(match_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    match_comment = crud.get_match_comments(db, match_id)
    return match_comment


@router.post("/{match_id}", response_model=MatchCommentRead, status_code=status.HTTP_201_CREATED)
def post_match_comment(match_id: int, payload: MatchCommentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    match_comment = crud.create_match_comment(db, user_id=current_user.id, match_id=match_id, content=payload.content)
    return match_comment
