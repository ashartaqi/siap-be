"""
SQLAlchemy database models.
Defines the database schema as Python classes.
"""
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

# class User(Base):
#     __tablename__ = "user"
#     id: Mapped[int] = mapped_column(primary_key=True)
