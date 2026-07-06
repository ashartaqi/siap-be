from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.schemas import AskRequest, AskResponse
from app.rag.service import ask_siap

router = APIRouter()


@router.post("", response_model=AskResponse)
def ask(request: AskRequest, db: Session = Depends(get_db)):
    return ask_siap(db, request.question)