from sqlalchemy import Column, Integer, String, DateTime, Boolean, func, ForeignKey
from app.core.db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    created_at = Column(DateTime, default=func.now())
    super_user = Column(Boolean, default=False)


class Club(Base):
    __tablename__ = "club"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    league_name = Column(String, index=True)
    nationality_name = Column(String, index=True)

    overall = Column(Integer, index=True)
    attack = Column(Integer, index=True)
    midfield = Column(Integer, index=True)
    defence = Column(Integer, index=True)

    home_stadium = Column(String, index=True)
    captain = Column(String, index=True)

class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True)
    short_name = Column(String, index=True)
    long_name = Column(String, index=True)
    player_positions = Column(String, index=True)
    overall = Column(Integer, index=True)
    age = Column(Integer, index=True)
    dob = Column(DateTime, index=True)
    height_cm = Column(Integer, index=True)
    weight_kg = Column(Integer, index=True)

    club_team_id = Column(Integer, ForeignKey("club.id", ondelete="CASCADE"))
    club_name = Column(String, index=True)

    nationality_id = Column(Integer, index=True)
    nationality_name = Column(String, index=True)

    preferred_foot = Column(String, index=True)
    weak_foot = Column(Integer, index=True)
    skill_moves = Column(Integer, index=True)
    work_rate = Column(String, index=True)

    pace = Column(Integer, index=True)
    shooting = Column(Integer, index=True)
    passing = Column(Integer, index=True)
    dribbling = Column(Integer, index=True)
    defending = Column(Integer, index=True)
    physic = Column(Integer, index=True)

    player_face_url = Column(String, index=True)