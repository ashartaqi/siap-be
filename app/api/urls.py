import app
from fastapi import APIRouter
from app.api.routes import players, teams, user, fixtures_and_standings, votes, custom_player,dream_team
from app.api.routes import players, teams, user, fixtures_and_standings, votes, custom_player

api_router = APIRouter()
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(teams.router, prefix="/teams", tags=["teams"])
api_router.include_router(players.router, prefix="/players", tags=["players"])
api_router.include_router(fixtures_and_standings.router, prefix="/live", tags=["live"])
api_router.include_router(votes.router, prefix="/votes", tags=["votes"])
api_router.include_router(custom_player.router, prefix="/custom-player", tags=["Custom Players"])
api_router.include_router(dream_team.router,prefix="/dream-team",tags=["Dream Team"])