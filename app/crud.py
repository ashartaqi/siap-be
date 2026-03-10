from sqlalchemy.orm import Session
from app.core.security import verify_password, get_password_hash
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from app.models import User


def create_user(db: Session, username: str, email: str, password: str, super_user: bool = False):
    hashed_pw = get_password_hash(password)
    user = User(username=username, email=email, password=hashed_pw, super_user=super_user)
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Username or email already exists")
    return user


def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if user and verify_password(password, user.password):
        return user
    return None

