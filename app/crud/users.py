from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from datetime import datetime, timezone, timedelta
from app.core.security import verify_password, get_password_hash, hash_refresh_token
from app.models import User, RefreshToken
from app.constants import DAILY_LOGIN_REWARD, INITIAL_BB_BALANCE

def create(db: Session, model_item, error_msg: str = "Item already exists or an error occured"):
    try:
        db.add(model_item)
        db.commit()
        db.refresh(model_item)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    return model_item

def create_user(db: Session, username: str, email: str, first_name: str, last_name: str, password: str, super_user: bool = False):
    hashed_pw = get_password_hash(password)
    user = User(
        username=username, 
        email=email,
        first_name=first_name, 
        last_name=last_name, 
        password=hashed_pw, 
        super_user=super_user,
        bb_balance=INITIAL_BB_BALANCE # Initial gift
    )
    return create(db, user, "Username or email already exists")

def create_refresh_token(db: Session, user_id: int, plain_token: str) -> RefreshToken:
    token_entry = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(plain_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    return create(db, token_entry, "Error creating refresh token")

def get_and_validate_refresh_token(db: Session, plain_token: str) -> RefreshToken | None:
    token_entry = db.query(RefreshToken).filter(
        RefreshToken.token_hash == hash_refresh_token(plain_token)
    ).first()
    if not token_entry:
        return None
    expires_at = token_entry.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None
    return token_entry

def add_bb_reward(db: Session, user_id: int, amount: int):
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.bb_balance += amount
        db.commit()
    return user

def check_and_award_daily_login_reward(db: Session, user: User) -> int:
    try:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        already_rewarded = db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id,
            RefreshToken.created_at >= today_start,
        ).first()
        if not already_rewarded:
            reward = DAILY_LOGIN_REWARD
            user.bb_balance = (user.bb_balance or 0) + reward
            db.flush()
            return reward
    except Exception as e:
        print(f"Daily reward error: {e}")
    return 0

def rotate_refresh_token(db: Session, old_token_id: int, user_id: int, new_plain_token: str) -> RefreshToken:
    """Delete the old token and issue a new one atomically."""
    db.query(RefreshToken).filter(
        RefreshToken.id == old_token_id,
        RefreshToken.user_id == user_id,
    ).delete(synchronize_session=False)
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.expires_at < datetime.now(timezone.utc),
    ).delete(synchronize_session=False)
    new_entry = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(new_plain_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return new_entry

def revoke_refresh_token(db: Session, plain_token: str) -> None:
    db.query(RefreshToken).filter(
        RefreshToken.token_hash == hash_refresh_token(plain_token)
    ).delete(synchronize_session=False)
    db.commit()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if user and verify_password(password, user.password):
        return user
    return None


def reset_user_password(db: Session, email: str, current_password: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(current_password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )
    db.query(RefreshToken).filter(RefreshToken.user_id == user.id).delete(synchronize_session=False)
    user.password = get_password_hash(password)
    db.commit()
    db.refresh(user)
    return user
