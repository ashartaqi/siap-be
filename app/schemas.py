"""
Pydantic schemas for data validation and serialization.
Used for request bodies and response models in API routes.
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, model_validator, field_validator, ConfigDict

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
    player_positions: str

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


class Goalkeepers(BaseModel):
    id: Optional[int]

    short_name: str
    long_name: str
    player_positions: str

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

    diving: Optional[int] = None
    handling: Optional[int] = None
    kicking: Optional[int] = None
    positioning: Optional[int] = None
    reflexes: Optional[int] = None
    speed: Optional[int] = None

    player_face_url: Optional[str] = None

    class Config:
        from_attributes = True