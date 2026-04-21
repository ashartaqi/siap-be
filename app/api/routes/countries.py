from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import crud
from app.api.deps import get_db
from app.schemas import Fixtures, LeagueStandings
from app.api.constants import COUNTRIES

router = APIRouter()

@router.get("/countries")
def get_countries():
    return COUNTRIES