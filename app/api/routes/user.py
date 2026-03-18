from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.core.security import create_access_token
from app.crud import authenticate_user, create_user
from app.schemas import UserLogin, UserRegister, Token, RegisteredUser

router = APIRouter()

@router.post("/register", response_model=RegisteredUser)
def register(user: UserRegister, db: Session = Depends(get_db)):
    try:

        db_user = create_user(db, username=user.username, email=user.email, password=user.password, first_name=user.first_name, last_name=user.last_name)
        if not db_user:
            raise HTTPException(status_code=400, detail="User registration failed")
        token = create_access_token({"sub": db_user.email})

        resp = RegisteredUser.model_validate(db_user)
        resp.token = token
        return resp
    except HTTPException:
        raise
    except Exception as e:
        print("Registration error:", str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    try:
        db_user = authenticate_user(db, email=user.email, password=user.password)
        if not db_user:
            raise HTTPException(status_code=400, detail="Incorrect username or password")
        token = create_access_token({"sub": db_user.email})
        return {"token": token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        print("Login error:", str(e))
        raise HTTPException(status_code=400, detail=str(e))



