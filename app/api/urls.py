"""
Main API router.
Aggregates all individual route routers into a single router for the application.
"""
from fastapi import APIRouter
from app.api.routes import placeholder  # Example route

api_router = APIRouter()
api_router.include_router(placeholder.router, prefix="/placeholder", tags=["placeholder"])
