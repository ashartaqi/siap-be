from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    set_refresh_cookie,
    clear_refresh_cookie,
    get_current_user,
)
from app.models import User
from app.crud import (
    authenticate_user,
    create_refresh_token,
    create_user,
    get_and_validate_refresh_token,
    get_user_by_id,
    revoke_refresh_token,
    rotate_refresh_token,
    check_and_award_daily_login_reward
)
from app.schemas import AccessToken, RegisteredUser, UserLogin, UserRegister

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


@router.post("/login", response_model=AccessToken)
def login(user: UserLogin, response: Response, db: Session = Depends(get_db)):
    try:
        db_user = authenticate_user(db, email=user.email, password=user.password)
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        # Reward Logic: Daily Login
        reward = check_and_award_daily_login_reward(db, db_user)

        access_token = create_access_token({"sub": db_user.email})
        refresh_token = generate_refresh_token()
        create_refresh_token(db, db_user.id, refresh_token)
        set_refresh_cookie(response, refresh_token)
            
        return {
            "access_token": access_token, 
            "token_type": "bearer",
            "reward_amount": reward if reward > 0 else None
        }
    except HTTPException:
        raise
    except Exception as e:
        print("Login error:", str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/refresh", response_model=AccessToken)
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
):
    invalid_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )
    if not refresh_token:
        raise invalid_exc
    try:
        token_entry = get_and_validate_refresh_token(db, refresh_token)
        if not token_entry:
            raise invalid_exc

        user = get_user_by_id(db, token_entry.user_id)
        if not user:
            raise invalid_exc

        new_refresh_token = generate_refresh_token()
        rotate_refresh_token(db, token_entry.id, token_entry.user_id, new_refresh_token)
        new_access_token = create_access_token({"sub": user.email})
        
        set_refresh_cookie(response, new_refresh_token)
        return {"access_token": new_access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        print("Refresh token error:", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed",
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
):
    if refresh_token:
        revoke_refresh_token(db, refresh_token)
    clear_refresh_cookie(response)

@router.get("/me", response_model=RegisteredUser)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
