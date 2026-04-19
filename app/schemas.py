"""
Pydantic schemas for data validation and serialization.
Used for request bodies and response models in API routes.
"""
from typing import Optional, ClassVar, Set , List
from datetime import datetime
from pydantic import BaseModel, EmailStr, model_validator, field_validator, ConfigDict, Field

class UserLogin(BaseModel):
    email: str
    password: str

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    password: str
    confirm_password: str
    

    @field_validator("username")
    def username_must_not_have_at(cls, v):
        if "@" in v:
            raise ValueError("Username must not contain '@'")
        return v
    
    @model_validator(mode="after")
    def match_passwords(cls, values):
        if len(values.password) < 7:
            raise ValueError("Password length is too short")
        if values.password != values.confirm_password:
            raise ValueError("Passwords don't match")
        return values
    
class RegisteredUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    token: Optional[str] = None


class Token(BaseModel):
    token: str
    token_type: str


class Players(BaseModel):
    id: Optional[int]

    short_name: str
    long_name: str
    positions: List[str] = []

    overall: int
    age: int
    dob: Optional[datetime] = None

    height_cm: int
    weight_kg: int

    club_team_id: int
    club_name: str

    nationality_id: int
    nationality_name: str

    preferred_foot: str
    weak_foot: int
    skill_moves: int
    work_rate: Optional[str] = None

    pace: Optional[int] = None
    shooting: Optional[int] = None
    passing: Optional[int] = None
    dribbling: Optional[int] = None
    defending: Optional[int] = None
    physic: Optional[int] = None

    player_face_url: Optional[str] = None


    class Config:
        from_attributes = True

    @field_validator("positions", mode="before")
    @classmethod
    def flatten_positions(cls, v):
        if v and hasattr(v[0], "position"):
            return [p.position for p in v]
        return v

class Votes(BaseModel):
    id: int
    user_id: int
    fixture_id: int
    prediction_away_score: int
    prediction_home_score: int

    class Config:
        from_attributes = True

class Fixtures(BaseModel):
    id: int
    date: str
    home_team: str
    away_team: str
    league: Optional[str] = None
    status: Optional[str] = None
    away_team_score: Optional[str] = None
    home_team_score: Optional[str] = None
    winner: Optional[str] = None

    class Config:
        from_attributes = True


class LeagueStandings(BaseModel):
    id: int
    position: int
    team_name: str
    points: int
    played_games: int
    won: int
    draw: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    league: str

    class Config:
        from_attributes = True


class PlayerBase(BaseModel):
    VALID_POSITIONS: ClassVar[Set[str]] = {
        "LW", "ST", "RW", "CM", "CAM", "LM", "RM", "CF",
        "LWB", "RWB", "LB", "RB", "CB", "CDM", "GK"
    }

    VALID_FEET: ClassVar[Set[str]] = {"Left", "Right"}

    @field_validator("name" ,check_fields=False)
    @classmethod
    def name_not_empty(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        if len(v) > 100:
            raise ValueError("Name too long")
        return v

    @field_validator("position",check_fields=False)
    @classmethod
    def valid_position(cls, v):
        if v is None:
            return v
        v = v.upper()
        if v not in cls.VALID_POSITIONS:
            raise ValueError(f"Position must be one of {cls.VALID_POSITIONS}")
        return v

    @field_validator("preferred_foot",check_fields=False)
    @classmethod
    def valid_foot(cls, v):
        if v is None:
            return v
        v = v.capitalize()
        if v not in cls.VALID_FEET:
            raise ValueError("Preferred foot must be 'Left' or 'Right'")
        return v

    @field_validator("pace", "shooting", "passing", "dribbling", "defending", "physic",check_fields=False)
    @classmethod
    def stat_range(cls, v):
        if v is None:
            return v
        if not (1 <= v <= 99):
            raise ValueError("Each stat must be between 1 and 99")
        return v

    @model_validator(mode="after")
    def check_total(self):
        stats = [
            getattr(self, "pace", None),
            getattr(self, "shooting", None),
            getattr(self, "passing", None),
            getattr(self, "dribbling", None),
            getattr(self, "defending", None),
            getattr(self, "physic", None),
        ]

        # Only validate if all stats are present (important for UPDATE)
        if all(v is not None for v in stats):
            total = sum(stats)
            if total > 570:
                raise ValueError(f"Total cannot exceed 570. You used {total}.")
        return self


class CustomPlayerCreate(PlayerBase):
    name: str
    position: str
    nationality: str
    shirt_number: int
    preferred_foot: str
    pace: int
    shooting: int
    passing: int
    dribbling: int
    defending: int
    physic: int


class CustomPlayerUpdate(PlayerBase):
    name: Optional[str] = None
    position: Optional[str] = None
    nationality: Optional[str] = None
    shirt_number: Optional[int] = None
    preferred_foot: Optional[str] = None
    pace: Optional[int] = None
    shooting: Optional[int] = None
    passing: Optional[int] = None
    dribbling: Optional[int] = None
    defending: Optional[int] = None
    physic: Optional[int] = None

class CustomPlayerGet(CustomPlayerCreate):
    overall: int