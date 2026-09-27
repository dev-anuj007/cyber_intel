from typing import Optional

from sqlmodel import Field, SQLModel


class UserTable(SQLModel, table=True):
    __tablename__: str = "users"  # type: ignore
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    salt: str
    full_name: Optional[str] = Field(default=None)
    role: Optional[str] = Field(default="member")
    gemini_api_key: Optional[str] = None
    api_key: Optional[str] = None
    created_at: Optional[str] = Field(default=None)



