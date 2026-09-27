from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

from src.services.accounts.internals.repositories.reader import AccountReader
from src.services.accounts.internals.repositories.writer import AccountWriter
from src.services.accounts.protocols import (
    IAccountReader,
    IAccountsService,
    IAccountWriter,
)


@dataclass(frozen=True)
class AccountsServiceDependencyContext:
    reader: IAccountReader
    writer: IAccountWriter
    logger: Any
    db_service: Any
    db_path: Optional[Union[Path, str]] = None

    def get_connection(self):
        return self.db_service.get_connection()


def get_accounts_dependency_context(
    db_path: Optional[Union[Path, str]] = None,
    db_service: Optional[Any] = None,
    reader: Optional[IAccountReader] = None,
    writer: Optional[IAccountWriter] = None,
    logger: Optional[Any] = None,
) -> AccountsServiceDependencyContext:
    from src.services.database.database_service import DatabaseService
    from src.services.database.dependencies import default_database_service
    from src.services.logger.logger_service import get_logger

    resolved_db_service = db_service
    if resolved_db_service is None:
        if db_path is not None:
            resolved_db_service = DatabaseService(
                db_path=Path(db_path) if isinstance(db_path, str) else db_path
            )
        else:
            resolved_db_service = default_database_service

    return AccountsServiceDependencyContext(
        reader=reader if reader is not None else AccountReader(),
        writer=writer if writer is not None else AccountWriter(),
        logger=logger if logger is not None else get_logger("services.accounts"),
        db_service=resolved_db_service,
        db_path=db_path,
    )


def create_accounts_service(
    context: Optional[AccountsServiceDependencyContext] = None,
    **kwargs: Any,
) -> IAccountsService:
    from src.services.accounts.accounts_service import AccountsService

    if context is None:
        context = get_accounts_dependency_context(**kwargs)
    return AccountsService(context=context)


_default_accounts_service: Optional[IAccountsService] = None


def get_accounts_service() -> IAccountsService:
    global _default_accounts_service
    if _default_accounts_service is None:
        _default_accounts_service = create_accounts_service()
    return _default_accounts_service


class _LazyAccountsServiceProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_accounts_service(), name)


default_accounts_service: IAccountsService = _LazyAccountsServiceProxy()  # type: ignore
