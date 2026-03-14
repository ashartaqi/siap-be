from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import httpx
from app.api.deps import get_db
from app.crud import add_leagues
from app.schemas import Leagues
from app.models import League

router = APIRouter()

LEAGUES = [
    {"slug": "eng.1", "country": "England"},
    {"slug": "esp.1", "country": "Spain"},
    {"slug": "ita.1", "country": "Italy"},
    {"slug": "ger.1", "country": "Germany"},
    {"slug": "fra.1", "country": "France"},
]

@router.post("/fetch-leagues")
def fetch_and_store_leagues(db: Session = Depends(get_db)):
    for i, league in enumerate(LEAGUES, start=1):
        response = httpx.get(f"https://sports.core.api.espn.com/v3/sports/soccer/{league['slug']}")
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Failed to fetch {league['slug']}")
        
        data = response.json()
        name = data["displayName"]
        country = league["country"]
        add_leagues(db, id=i, name=name, country=country)

    return {"message": "Leagues stored successfully"}