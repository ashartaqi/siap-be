from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.core.security import create_access_token, create_refresh_token
from app.crud import authenticate_user, create_user, create_refresh_token_db, get_user_by_email, get_latest_refresh_token, delete_refresh_token_by_user, verify_refresh_token_db, delete_expired_refresh_tokens
from app.schemas import UserLogin, UserRegister, Token, RegisteredUser, RefreshRequest

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

        refresh_token = create_refresh_token()

        create_refresh_token_db(db, db_user.id, refresh_token)

        return {"token": token, "token_type": "bearer", "refresh_token": refresh_token}
    except HTTPException:
        raise
    except Exception as e:
        print("Login error:", str(e))
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/refresh")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    """
    Refresh an access token using a valid refresh token.
    
    Implements token rotation: old refresh token is deleted and new one issued.
    
    Returns:
        dict: New access token and refresh token
    """
    try:
        # Get user by email
        user = get_user_by_email(db, payload.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Get the latest refresh token from database
        token_entry = get_latest_refresh_token(db, user.id)
        if not token_entry:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No refresh token found. Please log in again."
            )
        
        # Verify the refresh token (checks expiration + hash validation)
        is_valid = verify_refresh_token_db(db, user.id, payload.refresh_token)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        
        # Token rotation: delete old token
        delete_refresh_token_by_user(db, user.id, token_entry.id)
        
        # Clean up any other expired tokens
        delete_expired_refresh_tokens(db, user.id)
        
        # Create new refresh token
        new_refresh_token = create_refresh_token()
        
        # Store new refresh token in database
        create_refresh_token_db(db, user.id, new_refresh_token)
        
        # Create new access token
        new_access_token = create_access_token({"sub": user.email})
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print("Refresh token error:", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error refreshing token"
        )