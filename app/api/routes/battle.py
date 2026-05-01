from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app import crud
from app.api.deps import get_db
from app.models import User, DreamTeam, CustomPlayer
from app.core.security import get_current_user
from app.schemas import DreamTeamGet as DreamTeamSchema, CustomPlayerGet as CustomPlayerSchema, MatchSimulationResult

router = APIRouter()

@router.get("/users")
def get_battle_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Fetch all user_ids who have either a dream team or a custom player
    users_with_teams = {u[0] for u in db.query(DreamTeam.user_id).all()}
    users_with_players = {u[0] for u in db.query(CustomPlayer.user_id).all()}
    
    user_ids = users_with_teams.union(users_with_players)
    if current_user.id in user_ids:
        user_ids.remove(current_user.id)
        
    if not user_ids:
        return []
        
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    
    return [
        {
            "id": u.id,
            "username": u.username,
            "has_team": u.id in users_with_teams,
            "has_player": u.id in users_with_players
        }
        for u in users
    ]

@router.get("/team/{user_id}", response_model=DreamTeamSchema)
def get_user_dream_team(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    team = crud.get_dream_team(db, user_id)
    if not team:
        raise HTTPException(status_code=404, detail="Dream team not found for this user")
    return team

@router.get("/player/{user_id}", response_model=CustomPlayerSchema)
def get_user_custom_player(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    player = crud.get_custom_player(db, user_id)
    if not player:
        raise HTTPException(status_code=404, detail=f"Custom player not found for user_id {user_id}")
    return player

@router.post("/reward")
def award_battle_reward(result: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # result: 'win', 'loss', 'draw'
    reward = 10 # Participation
    if result == 'win':
        reward += 40
    elif result == 'draw':
        reward += 10 
        
    current_user.bb_balance += reward
    db.commit()
    return {"new_balance": current_user.bb_balance, "reward": reward}

from app.core.engine import FootballEngine, EngineTeam, EnginePlayer

def _map_team_to_engine(team: DreamTeam, team_name: str) -> EngineTeam:
    engine_players = []
    for slot in team.slots:
        p = slot.player
        role = "MID"
        pos = slot.position
        if pos in ["ST", "LW", "RW", "CF", "LF", "RF"]:
            role = "FWD"
        elif pos in ["CB", "LB", "RB", "LWB", "RWB", "GK"]:
            role = "DEF"

        stamina = 100.0
        defense = 50.0
        passing = 50.0
        attack = 50.0
        finishing = 50.0

        if p.player_stats:
            stamina = float(p.player_stats.physic) if p.player_stats.physic else 100.0
            defense = float(p.player_stats.defending) if p.player_stats.defending else 50.0
            passing = float(p.player_stats.passing) if p.player_stats.passing else 50.0
            attack = float(p.player_stats.shooting) if p.player_stats.shooting else 50.0
            finishing = float(p.player_stats.shooting) if p.player_stats.shooting else 50.0
        elif p.goalkeeper_stats:
            defense = float(p.goalkeeper_stats.handling) if p.goalkeeper_stats.handling else 80.0
            passing = float(p.goalkeeper_stats.kicking) if p.goalkeeper_stats.kicking else 60.0
            attack = 10.0
            finishing = 10.0

        engine_players.append(EnginePlayer(
            name=p.short_name,
            role=role,
            attack=attack,
            passing=passing,
            defense=defense,
            finishing=finishing,
            stamina=stamina
        ))

    return EngineTeam(name=team_name, players=engine_players)

@router.post("/simulate/{opponent_id}", response_model=MatchSimulationResult)
def simulate_battle(opponent_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    my_team = crud.get_dream_team(db, current_user.id)
    if not my_team:
        raise HTTPException(status_code=400, detail="You do not have a Dream Team")

    opp_team = crud.get_dream_team(db, opponent_id)
    if not opp_team:
        raise HTTPException(status_code=400, detail="Opponent does not have a Dream Team")

    engine_me = _map_team_to_engine(my_team, current_user.username)
    
    opp_user = db.query(User).filter(User.id == opponent_id).first()
    opp_name = opp_user.username if opp_user else f"User {opponent_id}"
    engine_opp = _map_team_to_engine(opp_team, opp_name)

    engine = FootballEngine(engine_me, engine_opp)
    result = engine.simulate()

    reward = 10 # Participation
    winner = "draw"
    if result.score1 > result.score2:
        reward += 40
        winner = "me"
    elif result.score2 > result.score1:
        winner = "opponent"
    else:
        reward += 10

    current_user.bb_balance += reward
    db.commit()

    return {
        "score1": result.score1,
        "score2": result.score2,
        "stats": {
            "shots1": result.stats.shots1,
            "shots2": result.stats.shots2,
            "xg1": result.stats.xg1,
            "xg2": result.stats.xg2,
            "possession1": int((result.stats.possession1 / max(1, result.stats.possession1 + result.stats.possession2)) * 100),
            "possession2": int((result.stats.possession2 / max(1, result.stats.possession1 + result.stats.possession2)) * 100),
        },
        "log": result.log,
        "winner": winner,
        "reward": reward,
        "new_balance": current_user.bb_balance
    }
