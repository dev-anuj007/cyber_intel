from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from src.services.accounts.internals.repositories.models.asset import AssetTable
    from src.services.accounts.internals.repositories.models.cloud_provider import (
        CloudProviderTable,
    )
    from src.services.accounts.internals.repositories.models.domain import DomainTable
    from src.services.accounts.internals.repositories.models.hostname import (
        HostnameTable,
    )
    from src.services.accounts.internals.repositories.models.ip import IpTable
    from src.services.accounts.internals.repositories.models.port import PortTable
    from src.services.accounts.internals.repositories.models.product import ProductTable
    from src.services.accounts.internals.repositories.models.signal import SignalTable


class AccountBase(SQLModel):
    account_key: str = Field(unique=True, index=True)
    signal_count: int = Field(default=0)
    priority_tier: str = Field(default="tier_4_low")


class AccountTable(AccountBase, table=True):
    __tablename__: str = "accounts"  # type: ignore
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[str] = Field(default=None)

    domains: List["DomainTable"] = Relationship(back_populates="account")
    assets: List["AssetTable"] = Relationship(back_populates="account")
    ips: List["IpTable"] = Relationship(back_populates="account")
    hostnames: List["HostnameTable"] = Relationship(back_populates="account")
    ports: List["PortTable"] = Relationship(back_populates="account")
    products: List["ProductTable"] = Relationship(back_populates="account")
    cloud_providers: List["CloudProviderTable"] = Relationship(back_populates="account")
    signals: List["SignalTable"] = Relationship(back_populates="account")
