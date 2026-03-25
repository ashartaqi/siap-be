"""
Pydantic schemas for data validation and serialization.
Used for request bodies and response models in API routes.
"""
from typing import Optional
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
    name: str
    position: str
    overall: int
    age: int
    club: str
    nation: str
    foot: str
    pace: int
    shooting: int
    passing: int
    dribbling: int
    defending: int
    physic: int

    class Config:
        orm_mode = True