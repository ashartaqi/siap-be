from fastapi import APIRouter
from app.api.routes import placeholder, user, getTeams, getplayers

api_router = APIRouter()
api_router.include_router(placeholder.router, prefix="/placeholder", tags=["placeholder"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(getTeams.router, prefix="/teams", tags=["teams"])
api_router.include_router(getplayers.router, prefix="/players", tags=["players"])