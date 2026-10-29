"""Declarative base for ORM models.

Models map existing tables only. The schema is owned by hand-written migrations,
so `Base.metadata` is never used to create or alter tables.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
