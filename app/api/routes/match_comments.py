from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.models import User
from app.core.security import get_current_user
from app.schemas import MatchComment, MatchCommentCreate

router = APIRouter()

@router.get("/{match_id}", response_model=list[MatchComment])
def get_match_comments(match_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        comments = crud.get_match_comments(db, match_id)
        return comments
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{match_id}", response_model=MatchComment, status_code=status.HTTP_201_CREATED)
def post_match_comment(match_id: int, payload: MatchCommentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        comment = crud.create_match_comment(db, user_id=current_user.id, match_id=match_id, content=payload.content)
        return MatchComment(
            id=comment.id,
            user_id=comment.user_id,
            match_id=comment.match_id,
            username=current_user.username,
            content=comment.content,
            created_at=comment.created_at
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
