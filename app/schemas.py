"""
Pydantic schemas for data validation and serialization.
Used for request bodies and response models in API routes.
"""
from pydantic import BaseModel, EmailStr, validator

class UserLogin(BaseModel):
    email: str
    password: str

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str

    @validator("username")
    def username_must_not_have_at(cls, v):
        if "@" in v:
            raise ValueError("Username must not contain '@'")
        return v


class Token(BaseModel):
    access_token: str
    token_type: str

