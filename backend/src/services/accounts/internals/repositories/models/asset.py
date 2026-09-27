from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from src.services.accounts.internals.repositories.models.account import AccountTable


class AssetTable(SQLModel, table=True):
    __tablename__: str = "assets"  # type: ignore
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="accounts.id", index=True)
    ip: Optional[str] = None
    port: Optional[int] = None
    hostname: Optional[str] = None

    account: Optional["AccountTable"] = Relationship(back_populates="assets")
