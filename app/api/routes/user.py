from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.core.security import create_access_token
from app.crud import authenticate_user, create_user
from app.schemas import UserLogin, UserRegister, Token

router = APIRouter()

@router.post("/register", response_model=UserRegister)
def register(user: UserRegister, db: Session = Depends(get_db)):
    db_user = create_user(db, user.username, user.email, user.password)
    return db_user

@router.post("/login", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    try:
        db_user = authenticate_user(db, user.email, user.password)
        if not db_user:
            raise HTTPException(status_code=400, detail="Incorrect username or password")
        token = create_access_token({"sub": db_user.email})
        return {"access_token": token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        print("Login error:", e)
        raise HTTPException(status_code=500, detail="Internal server error")
