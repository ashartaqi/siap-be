from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.models import User
from app.core.security import get_current_user
from app.schemas import Players


router = APIRouter()

@router.post("/getPlayers", response_model=list[Players])
def get_players(
    db: Session = Depends(get_db),
    limit: int = 11,
    team_id: int = None,
    name: str = None,
    nationality_name: str = None,
    position: str = None,
    min_overall: int = None,
    max_overall: int = None,
    min_age: int = None,
    max_age: int = None,
    preferred_foot: str = None
):
    players = crud.get_players(
        db, limit, team_id, name, nationality_name, position,
        min_overall, max_overall, min_age, max_age, preferred_foot
    )

    # 2️⃣ Map to frontend-friendly keys (response_model)
    print (players[0])

    result = []
    for p in players:
        result.append(
            Players(
                name=p.short_name,  # or p.long_name
                position=p.player_positions,
                club=p.club_name or "",  # <-- use club_name directly
                nation=p.nationality_name or "",
                foot=p.preferred_foot or "",
                overall=p.overall or 0,
                age=p.age or 0,
                pace=p.pace or 0,
                shooting=p.shooting or 0,
                passing=p.passing or 0,
                dribbling=p.dribbling or 0,
                defending=p.defending or 0,
                physic=p.physic or 0
            )
        )

    return result

@router.post("/fav")
def add_favourite(db: Session = Depends(get_db),current_user: User = Depends(get_current_user), player: int = None):
    if player:
        return crud.add_fav_player(db, current_user.id, player)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Player ID is required")


@router.get("/fav")
def get_favourite(db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    return crud.get_fav_players(db, current_user.id)


@router.delete("/fav")
def remove_favourite(db: Session = Depends(get_db),current_user: User = Depends(get_current_user), player: int = None):
    if player:
        result = crud.remove_fav_player(db, current_user.id, player)
        return {"success": result}
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Player ID is required")