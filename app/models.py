from sqlalchemy import Column, Integer, String, DateTime, Boolean, func, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    first_name = Column(String, index=True)
    last_name = Column(String, index=True)
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
    logo_url = Column(String, index=True)


class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True)
    short_name = Column(String, index=True)
    long_name = Column(String, index=True)
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
    player_face_url = Column(String, index=True)

    player_stats = relationship("PlayerStats", back_populates="player", uselist=False, cascade="all, delete-orphan")
    goalkeeper_stats = relationship("GoalkeeperStats", back_populates="player", uselist=False, cascade="all, delete-orphan")
    positions = relationship("PlayerPos", back_populates="player", cascade="all, delete-orphan")


class PlayerPos(Base):
    __tablename__ = "positions"
    player_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), primary_key=True)
    position = Column(String(20), primary_key=True)

    player = relationship("Player", back_populates="positions")


class PlayerStats(Base):
    __tablename__ = "player_stats"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), nullable=False, unique=True)

    pace = Column(Integer, nullable=True)
    shooting = Column(Integer, nullable=True)
    passing = Column(Integer, nullable=True)
    dribbling = Column(Integer, nullable=True)
    defending = Column(Integer, nullable=True)
    physic = Column(Integer, nullable=True)

    player = relationship("Player", back_populates="player_stats")


class GoalkeeperStats(Base):
    __tablename__ = "goalkeeper_stats"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), nullable=False, unique=True)

    diving = Column(Integer, nullable=True)
    handling = Column(Integer, nullable=True)
    kicking = Column(Integer, nullable=True)
    positioning = Column(Integer, nullable=True)
    reflexes = Column(Integer, nullable=True)
    speed = Column(Integer, nullable=True)

    player = relationship("Player", back_populates="goalkeeper_stats")

    
class FavouriteClubs(Base):
    __tablename__ = "favourite_clubs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    club_id = Column(Integer, ForeignKey("club.id", ondelete="CASCADE"))
    
    
class FavouritePlayers(Base):
    __tablename__ = "favourite_players"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    player_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"))

# Legacy table for older matches
class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True, index=True)
    round = Column(String, nullable=True)
    date = Column(String, nullable=False)
    time = Column(String, nullable=True)
    team1 = Column(String, nullable=False)
    team2 = Column(String, nullable=False)
    score_ft = Column(String, nullable=True)
    winner = Column(String, nullable=True)
    league = Column(String, nullable=True)


class Fixtures(Base):
    __tablename__ = "fixtures"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, nullable=False)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)
    league = Column(String, nullable=True)
    status = Column(String, nullable=True)
    away_team_score = Column(String, nullable=True)
    home_team_score = Column(String, nullable=True)
    winner = Column(String, nullable=True)


class Votes(Base):
    __tablename__ = "votes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    fixture_id = Column(Integer, ForeignKey("fixtures.id", ondelete="CASCADE"))
    prediction_away_score = Column(Integer, nullable=False)
    prediction_home_score = Column(Integer, nullable=False)


class LeagueStandings(Base):
    __tablename__ = "league_standings"
    id = Column(Integer, primary_key=True, index=True)
    position = Column(Integer, nullable=False)
    team_name = Column(String, nullable=False)
    points = Column(Integer, nullable=False)
    played_games = Column(Integer, nullable=False)
    won = Column(Integer, nullable=False)
    draw = Column(Integer, nullable=False)
    lost = Column(Integer, nullable=False)
    goals_for = Column(Integer, nullable=False)
    goals_against = Column(Integer, nullable=False)
    goal_difference = Column(Integer, nullable=False)
    league = Column(String, nullable=False)
    logo_url = Column(String, nullable=True)

    forms = relationship("Form", backref="league_standing", cascade="all, delete")


class Form(Base):
    __tablename__ = "form"

    id = Column(Integer, primary_key=True)
    league_standing_id = Column(
        Integer,
        ForeignKey("league_standings.id", ondelete="CASCADE"),
        nullable=False
    )
    outcome = Column(String, nullable=False)


class CustomPlayer(Base):
    __tablename__ = "custom_players"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    position = Column(String(10), nullable=False)
    nationality = Column(String(100), nullable=False)
    shirt_number = Column(Integer, nullable=False)
    preferred_foot = Column(String(5), nullable=False)
    pace = Column(Integer, nullable=False)
    shooting = Column(Integer, nullable=False)
    passing = Column(Integer, nullable=False)
    dribbling = Column(Integer, nullable=False)
    defending = Column(Integer, nullable=False)
    physic = Column(Integer, nullable=False)
    overall = Column(Integer, nullable=False)

class DreamTeam(Base):
    __tablename__ = "dream_team"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    formation = Column(String(20),nullable=False)
    total_score = Column(Integer, nullable=False)
    slots = relationship("DreamTeamSlot", uselist=True, cascade="all, delete-orphan")


class DreamTeamSlot(Base):
    __tablename__ = "dream_team_slot"

    id = Column(Integer, primary_key=True, index=True)
    dream_team_id = Column(Integer, ForeignKey("dream_team.id", ondelete="CASCADE"), nullable=False)
    position = Column(String(10),nullable=False)
    col = Column(Integer,nullable=True)
    row = Column(Integer,nullable=True)
    player_id =Column(Integer,ForeignKey("players.id",ondelete = "CASCADE"), nullable = False)
   

