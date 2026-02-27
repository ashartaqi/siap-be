from fastapi import APIRouter
from app.api.routes import placeholder, user

api_router = APIRouter()
api_router.include_router(placeholder.router, prefix="/placeholder", tags=["placeholder"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
