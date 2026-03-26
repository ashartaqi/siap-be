from fastapi import APIRouter
from app.api.routes import players, teams, user, goalkeepers
from app.api.routes import players, teams, user, fixtures_and_standings, votes

api_router = APIRouter()
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(teams.router, prefix="/teams", tags=["teams"])
api_router.include_router(players.router, prefix="/players", tags=["players"])
api_router.include_router(goalkeepers.router, prefix="/goalkeepers", tags=["goalkeepers"])
api_router.include_router(fixtures_and_standings.router, prefix="/live", tags=["live"])
api_router.include_router(votes.router, prefix="/votes", tags=["votes"])