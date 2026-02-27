from sqlalchemy.orm import Session
from app.core.security import verify_password, get_password_hash
from app.models import User


def create_user(db: Session, username: str, email: str, password: str):
    hashed_pw = get_password_hash(password)
    user = User(username=username, email=email, password=hashed_pw)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if user and verify_password(password, user.password):
        return user
    return None

