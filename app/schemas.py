"""
Pydantic schemas for data validation and serialization.
Used for request bodies and response models in API routes.
"""
from typing import Optional, ClassVar, Set, List, Literal
from datetime import datetime
from pydantic import BaseModel, EmailStr, model_validator, field_validator, ConfigDict
from app.constants import VALID_PLAYER_POSITIONS, VALID_PREFERRED_FEET, PLAYER_STAT_MIN, PLAYER_STAT_MAX, PLAYER_TOTAL_STATS_MAX, INITIAL_BB_BALANCE


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
    bb_balance: int = INITIAL_BB_BALANCE
    token: Optional[str] = None


class AccessToken(BaseModel):
    access_token: str
    token_type: str
    reward_amount: int = 0


class ShopUnlockResponse(BaseModel):
    message: str
    new_balance: int


class BattleUser(BaseModel):
    id: int
    username: str
    has_team: bool
    has_player: bool


class BattleRewardResponse(BaseModel):
    new_balance: int
    reward: int


class PlayerStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pace: Optional[int] = None
    shooting: Optional[int] = None
    passing: Optional[int] = None
    dribbling: Optional[int] = None
    defending: Optional[int] = None
    physic: Optional[int] = None


class GoalkeeperStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    diving: Optional[int] = None
    handling: Optional[int] = None
    kicking: Optional[int] = None
    positioning: Optional[int] = None
    reflexes: Optional[int] = None
    speed: Optional[int] = None


class Players(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    short_name: str
    long_name: str

    positions: List[str] = []

    overall: int
    dob: Optional[datetime] = None

    height_cm: int
    weight_kg: int

    club_team_id: Optional[int] = None
    club_name: Optional[str] = None

    nationality_name: str

    preferred_foot: str
    weak_foot: int
    skill_moves: int
    work_rate: Optional[str] = None

    player_stats: Optional[PlayerStats] = None
    goalkeeper_stats: Optional[GoalkeeperStats] = None

    player_face_url: Optional[str] = None
    is_unlocked: bool = False

    @field_validator("positions", mode="before")
    @classmethod
    def flatten_positions(cls, v):
        if v and hasattr(v[0], "position"):
            return [p.position for p in v]
        return v


class Team(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    league_name: Optional[str] = None
    nationality_name: Optional[str] = None
    overall: Optional[int] = None
    attack: Optional[int] = None
    midfield: Optional[int] = None
    defence: Optional[int] = None
    home_stadium: Optional[str] = None
    logo_url: Optional[str] = None


class Votes(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    fixture_id: int
    prediction_away_score: int
    prediction_home_score: int


class VoteCreate(BaseModel):
    fixture_id: int
    prediction_home_score: int
    prediction_away_score: int


class VoteWithUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    username: str
    first_name: str
    fixture_id: int
    prediction_home_score: int
    prediction_away_score: int


class Fixtures(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: str
    home_team: str
    away_team: str
    league: Optional[str] = None
    status: Optional[str] = None
    away_team_score: Optional[str] = None
    home_team_score: Optional[str] = None
    winner: Optional[str] = None


class LeagueStandings(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    logo_url: Optional[str] = None
    forms: List[str] = []

    @field_validator("forms", mode="before")
    @classmethod
    def flatten_forms(cls, v):
        if v and hasattr(v[0], "outcome"):
            return [f.outcome for f in v]
        return v


class PlayerBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    VALID_POSITIONS: ClassVar[Set[str]] = {pos for group in VALID_PLAYER_POSITIONS.values() for pos in group}
    VALID_FEET: ClassVar[Set[str]] = set(VALID_PREFERRED_FEET)

    @field_validator("name", check_fields=False)
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

    @field_validator("position", check_fields=False)
    @classmethod
    def valid_position(cls, v):
        if v is None:
            return v
        v = v.upper()
        if v not in cls.VALID_POSITIONS:
            raise ValueError(f"Position must be one of {cls.VALID_POSITIONS}")
        return v

    @field_validator("preferred_foot", check_fields=False)
    @classmethod
    def valid_foot(cls, v):
        if v is None:
            return v
        v = v.capitalize()
        if v not in cls.VALID_FEET:
            raise ValueError("Preferred foot must be 'Left' or 'Right'")
        return v

    @field_validator("pace", "shooting", "passing", "dribbling", "defending", "physic", check_fields=False)
    @classmethod
    def stat_range(cls, v):
        if v is None:
            return v
        if not (PLAYER_STAT_MIN <= v <= PLAYER_STAT_MAX):
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
        if all(v is not None for v in stats):
            total = sum(stats)
            if total > PLAYER_TOTAL_STATS_MAX:
                raise ValueError(f"Total cannot exceed {PLAYER_TOTAL_STATS_MAX}. You used {total}.")
        return self


class CustomPlayerCreate(PlayerBase):
    name: str
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
    position: str
    overall: int


class FormationBase(BaseModel):
    formation: Literal["4-3-3", "4-4-2", "4-2-3-1", "3-5-2", "5-3-2", "3-4-3"]


class DreamTeamSlotCreate(BaseModel):
    position: str
    player_id: int
    row: Optional[int] = None
    col: Optional[int] = None


class DreamTeamCreate(FormationBase):
    slots: List[DreamTeamSlotCreate]


class DreamTeamSlotGet(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: str
    row: Optional[int] = None
    col: Optional[int] = None
    player_id: int
    player: Optional[Players] = None


class DreamTeamSlotUpdate(BaseModel):
    player_id: int


class DreamTeamGet(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    formation: str
    slots: List[DreamTeamSlotGet]
    total_score: int


class ChatMessageCreate(BaseModel):
    content: str


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    username: str
    content: str
    created_at: datetime
    reward_amount: int = 0


class MatchCommentCreate(BaseModel):
    content: str


class MatchCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    match_id: int
    username: str
    content: str
    created_at: datetime
    reward_amount: int = 0


class MatchSimulationStats(BaseModel):
    shots1: int
    shots2: int
    xg1: float
    xg2: float
    possession1: int
    possession2: int


class MatchSimulationResult(BaseModel):
    score1: int
    score2: int
    stats: MatchSimulationStats
    log: List[str]
    winner: Literal["me", "opponent", "draw"]
    reward: int
    new_balance: int
