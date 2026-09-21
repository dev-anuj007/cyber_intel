"""SQLModel models for accounts and related entity tables."""

from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


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


class DomainTable(SQLModel, table=True):
    __tablename__: str = "domains"  # type: ignore
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="accounts.id", index=True)
    domain: str

    account: Optional[AccountTable] = Relationship(back_populates="domains")


class AssetTable(SQLModel, table=True):
    __tablename__: str = "assets"  # type: ignore
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="accounts.id", index=True)
    ip: Optional[str] = None
    port: Optional[int] = None
    hostname: Optional[str] = None

    account: Optional[AccountTable] = Relationship(back_populates="assets")


class IpTable(SQLModel, table=True):
    __tablename__: str = "ips"  # type: ignore
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="accounts.id", index=True)
    ip: str

    account: Optional[AccountTable] = Relationship(back_populates="ips")


class HostnameTable(SQLModel, table=True):
    __tablename__: str = "hostnames"  # type: ignore
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="accounts.id", index=True)
    hostname: str

    account: Optional[AccountTable] = Relationship(back_populates="hostnames")


class PortTable(SQLModel, table=True):
    __tablename__: str = "ports"  # type: ignore
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="accounts.id", index=True)
    port: int

    account: Optional[AccountTable] = Relationship(back_populates="ports")


class ProductTable(SQLModel, table=True):
    __tablename__: str = "products"  # type: ignore
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="accounts.id", index=True)
    product: str

    account: Optional[AccountTable] = Relationship(back_populates="products")


class CloudProviderTable(SQLModel, table=True):
    __tablename__: str = "cloud_providers"  # type: ignore
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="accounts.id", index=True)
    provider: str

    account: Optional[AccountTable] = Relationship(back_populates="cloud_providers")


class SignalTable(SQLModel, table=True):
    __tablename__: str = "signals"  # type: ignore
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="accounts.id", index=True)
    name: str
    severity: str
    category: str
    evidence: str

    account: Optional[AccountTable] = Relationship(back_populates="signals")


class AIScoreTable(SQLModel, table=True):
    __tablename__: str = "ai_scores"  # type: ignore
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    account_key: str = Field(index=True)
    version: int = Field(default=1)
    score: int
    priority_tier: str
    key_risks: str
    suggested_outreach: str
    score_rationale: Optional[str] = ""
    model_version: str
    model_name: Optional[str] = "gemini-3.1-flash-lite"
    tokens_used: Optional[str] = None
    latency_ms: Optional[int] = 0
    cost_usd: Optional[float] = 0.0
    scored_at: Optional[str] = None
    is_latest: Optional[int] = 1
