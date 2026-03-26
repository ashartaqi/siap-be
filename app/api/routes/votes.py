from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.models import User
from app.core.security import get_current_user
from app.schemas import Votes
from pydantic import BaseModel


router = APIRouter()

class CreateVoteRequest(BaseModel):
    fixture_id: int
    prediction_home_score: int
    prediction_away_score: int

@router.get("/all-votes", response_model=list[Votes])
def get_votes(
    db: Session = Depends(get_db),
    limit: int = 11,
    fixture_id: int = None
):
    try:
        votes = crud.get_votes(db, limit, fixture_id)
        return votes
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/")
def create_vote(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    vote_data: CreateVoteRequest = Body(...)
):
    return crud.create_vote(
        db, current_user.id, vote_data.fixture_id, 
        vote_data.prediction_home_score, vote_data.prediction_away_score
    )


@router.get("/")
def get_user_votes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return crud.get_user_votes(db, current_user.id)


@router.delete("/")
def delete_vote(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    vote_id: int = None
):
    if vote_id:
        result = crud.delete_vote(db, current_user.id, vote_id)
        return {"success": result}
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="vote_id is required")
