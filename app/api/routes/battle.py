import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.models import User
from app.core.security import get_current_user
from app.schemas import (
    DreamTeamGet as DreamTeamSchema,
    CustomPlayerGet as CustomPlayerSchema,
    MatchSimulationResult,
    BattleUser,
)
from app.constants import (
    BATTLE_PARTICIPATION_REWARD,
    BATTLE_WIN_REWARD,
    BATTLE_DRAW_REWARD,
)
from app.api.utils.engine import (FootballEngine, 
        map_team_to_engine,
        to_player_dict,
        attack_score,
        defense_score,
        position_bonus
)

router = APIRouter()


@router.get("/users", response_model=list[BattleUser])
def get_battle_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    users, users_with_teams, users_with_players = crud.get_battle_users_from_db(db, current_user.id)
    return [
        BattleUser(
            id=u.id,
            username=u.username,
            has_team=u.id in users_with_teams,
            has_player=u.id in users_with_players,
        )
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


@router.post("/team/simulate/{opponent_id}", response_model=MatchSimulationResult)
def simulate_team_battle(opponent_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    my_team = crud.get_dream_team(db, current_user.id)
    if not my_team:
        raise HTTPException(status_code=400, detail="You do not have a Dream Team")

    opp_team = crud.get_dream_team(db, opponent_id)
    if not opp_team:
        raise HTTPException(status_code=400, detail="Opponent does not have a Dream Team")

    opp_user = crud.get_user_by_id(db, opponent_id)
    opp_name = opp_user.username if opp_user else f"User {opponent_id}"

    engine = FootballEngine(
        map_team_to_engine(my_team, current_user.username),
        map_team_to_engine(opp_team, opp_name),
    )
    result = engine.simulate()

    reward = BATTLE_PARTICIPATION_REWARD
    if result.score1 > result.score2:
        reward += BATTLE_WIN_REWARD
        winner = "me"
    elif result.score2 > result.score1:
        winner = "opponent"
    else:
        reward += BATTLE_DRAW_REWARD
        winner = "draw"

    updated_user = crud.add_bb_reward(db, current_user.id, reward)
    total = max(1, result.stats.possession1 + result.stats.possession2)

    match_result = MatchSimulationResult(
        score1=result.score1,
        score2=result.score2,
        stats={
            "shots1": result.stats.shots1,
            "shots2": result.stats.shots2,
            "xg1": result.stats.xg1,
            "xg2": result.stats.xg2,
            "possession1": int(result.stats.possession1 / total * 100),
            "possession2": int(result.stats.possession2 / total * 100),
        },
        log=result.log,
        winner=winner,
        reward=reward,
        new_balance=updated_user.bb_balance,
    )

    return match_result

@router.post("/player/simulate/{opponent_id}", response_model=MatchSimulationResult)
def simulate_player_battle(
    opponent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    my_team = crud.get_dream_team(db, current_user.id)
    if not my_team:
        raise HTTPException(status_code=400, detail="You do not have a Dream Team")

    opp_team = crud.get_dream_team(db, opponent_id)
    if not opp_team:
        raise HTTPException(status_code=400, detail="Opponent does not have a Dream Team")

    opp_user = crud.get_user_by_id(db, opponent_id)
    opp_name = opp_user.username if opp_user else f"User {opponent_id}"

    p1 = to_player_dict(my_team)
    p2 = to_player_dict(opp_team)

    b1, b2 = position_bonus(p1), position_bonus(p2)
    p1_attack = attack_score(p1) * b1["attack"]
    p1_def    = defense_score(p1) * b1["defense"]
    p2_attack = attack_score(p2) * b2["attack"]
    p2_def    = defense_score(p2) * b2["defense"]

    score1, score2, log = 0, 0, []
    for minute in range(10):
        if p1_attack * random.uniform(0.8, 1.2) > p2_def * random.uniform(0.8, 1.2):
            score1 += 1
            log.append(f"{current_user.username} scores at chance {minute + 1}")
        if p2_attack * random.uniform(0.8, 1.2) > p1_def * random.uniform(0.8, 1.2):
            score2 += 1
            log.append(f"{opp_name} scores at chance {minute + 1}")

    if score1 > score2:
        winner, reward = "me", BATTLE_PARTICIPATION_REWARD + BATTLE_WIN_REWARD
    elif score2 > score1:
        winner, reward = "opponent", BATTLE_PARTICIPATION_REWARD
    else:
        winner, reward = "draw", BATTLE_PARTICIPATION_REWARD + BATTLE_DRAW_REWARD

    updated_user = crud.add_bb_reward(db, current_user.id, reward)

    total_goals = max(score1 + score2, 1)
    return MatchSimulationResult(
        score1=score1,
        score2=score2,
        stats={
            "shots1": 10,
            "shots2": 10,
            "xg1": round(p1_attack / (p1_attack + p2_attack) * total_goals, 2),
            "xg2": round(p2_attack / (p1_attack + p2_attack) * total_goals, 2),
            "possession1": int(p1_attack / (p1_attack + p2_attack) * 100),
            "possession2": int(p2_attack / (p1_attack + p2_attack) * 100),
        },
        log=log,
        winner=winner,
        reward=reward,
        new_balance=updated_user.bb_balance,
    )