from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.rate_limit import limiter, ASK_LIMIT
from app.schemas import AskRequest, AskResponse
from app.rag.service import ask_siap

router = APIRouter()


@router.post("", response_model=AskResponse)
@limiter.limit(ASK_LIMIT)
def ask(request: Request, ask_request: AskRequest, db: Session = Depends(get_db)):
    return ask_siap(db, ask_request.question)