"""
Placeholder API routes.
Serves as an example for creating new route modules.
"""
from fastapi import APIRouter, Depends
from app.models import User
from app.core.security import get_current_user


router = APIRouter()

@router.get("/")
def read_items(current_user: User = Depends(get_current_user)):
    return [{"item_id": "Foo"}, {"item_id": "Bar"}]
