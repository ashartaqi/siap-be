from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.models import User
from app.core.security import get_current_user
from app.core.DreamTeamSuggestion import suggestion
from app.schemas import DreamTeamCreate, DreamTeamGet, DreamTeamSlotUpdate
from app.api.constants import FORMATIONS

router = APIRouter()


@router.post("", response_model=DreamTeamGet, status_code=status.HTTP_201_CREATED)
def create_dream_team(payload: DreamTeamCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    team = crud.get_dream_team(db, current_user.id)
    if team:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You already have a dream team.")
    try:
        team = crud.create_dream_team(db, user_id=current_user.id, formation=payload.formation, slots=payload.slots)
        return team
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=Optional[DreamTeamGet])
def get_dream_team(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    team = crud.get_dream_team(db, current_user.id)
    return team


@router.put("" ,response_model=DreamTeamGet)
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


@router.delete("")
def delete_dream_team(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = crud.delete_dream_team(db, current_user.id)
    if result:
        return {"success": True}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dream team not found")

@router.get("/{formation}")
def get_optimized_dream_team(formation: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):

    team = suggestion(formation)

    formation_data = next((f for f in FORMATIONS if f["id"] == formation), None)
    if not formation_data:
        raise HTTPException(status_code=400, detail="Invalid formation")

    rows = formation_data["rows"]

    outfield_players = []
    for group in reversed(team[1:]):
        outfield_players.extend(group)

    slots = []
    slot_id = 1
    total_overall = 0
    player_index = 0

    for row_index, row_positions in enumerate(rows):
        for col, position in enumerate(row_positions):
            player = outfield_players[player_index]
            slots.append({
                "id": slot_id,
                "position": position,
                "row": row_index,
                "col": col,
                "player_id": player.id,
                "player": player
            })
            total_overall += player.overall
            slot_id += 1
            player_index += 1

    # GK last
    gk = team[0][0]
    slots.append({
        "id": slot_id,
        "position": "GK",
        "row": None,
        "col": None,
        "player_id": gk.id,
        "player": gk
    })
    total_overall += gk.overall

    return {
        "id": 1,
        "formation": formation,
        "slots": slots,
        "total_score": total_overall // 11
    }