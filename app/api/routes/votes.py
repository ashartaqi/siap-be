from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.models import User
from app.core.security import get_current_user
from app.schemas import Votes, VoteCreate, VoteWithUser


router = APIRouter()


@router.get("/my-votes", response_model=list[Votes])
def get_my_votes(db: Session = Depends(get_db), current_user: User = Depends(get_current_user),):
    return crud.get_user_votes(db, current_user.id)


@router.get("/all-votes", response_model=list[VoteWithUser])
def get_fixture_votes(fixture_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user), limit: int = 50,):
    return crud.get_votes_with_users(db, fixture_id, limit)


@router.post("", response_model=Votes)
def create_vote(vote_data: VoteCreate = Body(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user),):
    return crud.create_vote(
        db, current_user.id, vote_data.fixture_id,
        vote_data.prediction_home_score, vote_data.prediction_away_score
    )


@router.put("", response_model=Votes)
def update_vote(vote_data: VoteCreate = Body(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user),):
    return crud.update_vote(
        db, current_user.id, vote_data.fixture_id,
        vote_data.prediction_home_score, vote_data.prediction_away_score
    )



@router.delete("")
def delete_vote(db: Session = Depends(get_db), current_user: User = Depends(get_current_user), vote_id: int = None,):
    result = crud.delete_vote(db, current_user.id, vote_id)
    return {"success": result}
