from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.models import User
from app.core.security import get_current_user
from app.schemas import DreamTeamCreate, DreamTeamGet, DreamTeamSlotUpdate

router = APIRouter()


@router.post("/", response_model=DreamTeamGet, status_code=status.HTTP_201_CREATED)
def create_dream_team(payload: DreamTeamCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    team = crud.get_dream_team(db, current_user.id)
    if team:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You already have a dream team.")
    try:
        team = crud.create_dream_team(db, user_id=current_user.id, formation=payload.formation, slots=payload.slots)
        return team
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=DreamTeamGet)
def get_dream_team(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    team = crud.get_dream_team(db, current_user.id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No dream team found")
    return team


@router.put("/", response_model=DreamTeamGet)
def update_dream_team(payload: DreamTeamCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    team = crud.get_dream_team(db, current_user.id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Create a dream team first.")
    try:
        team = crud.update_dream_team(db, user_id=current_user.id, formation=payload.formation, slots=payload.slots)
        return team
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/slot/{slot_id}", response_model=DreamTeamGet)
def update_dream_team_slot(slot_id: int, payload: DreamTeamSlotUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        team = crud.update_dream_team_slot(db, user_id=current_user.id, slot_id=slot_id, player_id=payload.player_id)
        return team
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/")
def delete_dream_team(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = crud.delete_dream_team(db, current_user.id)
    if result:
        return {"success": True}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dream team not found")