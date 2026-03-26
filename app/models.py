from sqlalchemy import Column, Integer, String, DateTime, Boolean, func, ForeignKey
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

class Goalkeeper(Base):
    __tablename__ = "goalkeepers"
    
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

    goalkeeping_diving = Column(Integer, index=True)
    goalkeeping_handling = Column(Integer, index=True)
    goalkeeping_kicking = Column(Integer, index=True)
    goalkeeping_positioning = Column(Integer, index=True)
    goalkeeping_reflexes = Column(Integer, index=True)
    goalkeeping_speed = Column(Integer, index=True)

    player_face_url = Column(String, index=True)
    
    
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
