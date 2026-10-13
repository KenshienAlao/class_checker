"""Persistence for application user profiles."""

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.user import User


class AuthenticationRepository:
    """Reads and writes ``users`` profile rows."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user(self, user_id: UUID) -> User | None:
        """Return the profile for ``user_id``, or ``None``."""
        return self.db.scalar(select(User).where(User.id == user_id))

    def exist_by_email(self, email: str) -> bool:
        """Return whether a profile with ``email`` already exists."""
        return bool(self.db.scalar(select(exists().where(User.email == email))))

    def get_user_by_email(self, email: str) -> User | None:
        """Return the profile for ``email``, or ``None``."""
        return self.db.scalar(select(User).where(User.email == email))

    def create_user(self, user: User) -> User:
        """Persist a new user profile.

        Returns the committed row with server-generated columns populated.
        """
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
