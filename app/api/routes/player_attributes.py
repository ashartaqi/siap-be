from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.schemas import Fixtures, LeagueStandings
from app.api.constants import (
    VALID_PLAYER_POSITIONS,
    VALID_PREFERRED_FEET,
    PLAYER_STAT_MIN,
    PLAYER_STAT_MAX,
    PLAYER_TOTAL_STATS_MAX,
    ALL_POSITIONS,
    STAT_FIELD_MAP,
    DEFAULT_IDENTITY,
    DEFAULT_STATS,
)

router = APIRouter()

@router.get("/player-pos")
def get_player_positions():
    return VALID_PLAYER_POSITIONS

@router.get("/preferred-feet")
def get_preferred_feet():
    return VALID_PREFERRED_FEET

@router.get("/stat-min")
def get_stat_minimum():
    return PLAYER_STAT_MIN

@router.get("/stat-max")
def get_stat_maximum():
    return PLAYER_STAT_MAX

@router.get("/total-stats")
def get_total_stats():
    return PLAYER_TOTAL_STATS_MAX

@router.get("/all-positions")
def get_all_positions():
    return ALL_POSITIONS

@router.get("/stat-field")
def get_stat_field():
    return STAT_FIELD_MAP

@router.get("/default-identity")
def get_default_identity():
    return DEFAULT_IDENTITY

@router.get("/default-stats")
def get_default_stats():
    return DEFAULT_STATS