from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.models import User
from app.core.security import get_current_user
from app.core.DreamTeamSuggestion import suggestion
from app.schemas import DreamTeamCreate, DreamTeamGet, DreamTeamSlotUpdate

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

    parts = formation.split("-")
    num_def = int(parts[0])
    num_mid = int(parts[1])
    num_att = int(parts[2])

    position_labels = (
        ["LW", "ST", "RW"][:num_att] +                          # ATT
        (["CM"] * num_mid) +                                     # MID
        (["LB"] + ["CB"] * (num_def - 2) + ["RB"]) +            # DEF
        ["GK"]                                                    # GK
    )

    slots = []
    slot_id = 1
    total_overall = 0

    # ATT row
    for col, player in enumerate(team[3]):
        slots.append({
            "id": slot_id,
            "position": position_labels[slot_id - 1],
            "row": 0,
            "col": col,
            "player_id": player.id,
            "player": player
        })
        total_overall += player.overall
        slot_id += 1

    # MID row
    for col, player in enumerate(team[2]):
        slots.append({
            "id": slot_id,
            "position": "CM",
            "row": 1,
            "col": col,
            "player_id": player.id,
            "player": player
        })
        total_overall += player.overall
        slot_id += 1

    # DEF row
    def_positions = ["LB"] + ["CB"] * (num_def - 2) + ["RB"]
    for col, (player, pos) in enumerate(zip(team[1], def_positions)):
        slots.append({
            "id": slot_id,
            "position": pos,
            "row": 2,
            "col": col,
            "player_id": player.id,
            "player": player
        })
        total_overall += player.overall
        slot_id += 1

    # GK
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