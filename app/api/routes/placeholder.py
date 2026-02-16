"""
Placeholder API routes.
Serves as an example for creating new route modules.
"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def read_items():
    return [{"item_id": "Foo"}, {"item_id": "Bar"}]
