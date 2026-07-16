from socket import gaierror

from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError


class DatabaseConnectionError(RuntimeError):
    """Raised when a workflow cannot initialize or reach the database safely."""


def database_target(database_url: str) -> str:
    try:
        parsed = make_url(database_url)
    except Exception:
        return "<unparseable database_url>"

    host = parsed.host or "<no host>"
    port = f":{parsed.port}" if parsed.port else ""
    database = f"/{parsed.database}" if parsed.database else ""
    return f"{parsed.drivername}://{host}{port}{database}"


def walk_exception_chain(exc: BaseException) -> list[BaseException]:
    seen: set[int] = set()
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        orig = getattr(current, "orig", None)
        if isinstance(current, SQLAlchemyError) and isinstance(orig, BaseException):
            current = orig
        else:
            current = current.__cause__ or current.__context__
    return chain


def database_error_message(
    *,
    database_url: str,
    exc: BaseException,
    workflow_name: str,
    secret_ref: str = "DATABASE_URL",
) -> str:
    target = database_target(database_url)
    chain = walk_exception_chain(exc)

    if target == "<unparseable database_url>":
        return (
            f"{workflow_name} could not parse DATABASE_URL. Check {secret_ref}: {exc}"
        )

    dns_error = next((item for item in chain if isinstance(item, gaierror)), None)
    if dns_error is not None:
        return (
            f"{workflow_name} could not resolve the Postgres host from DATABASE_URL "
            f"({target}). Check {secret_ref} and make sure the host is reachable "
            f"from workflow pods: {dns_error}"
        )

    refused = next(
        (item for item in chain if isinstance(item, ConnectionRefusedError)), None
    )
    if refused is not None:
        return (
            f"{workflow_name} reached the configured Postgres host but the connection "
            f"was refused ({target}). Check the service, port, and network policy: "
            f"{refused}"
        )

    timeout = next((item for item in chain if isinstance(item, TimeoutError)), None)
    if timeout is not None:
        return (
            f"{workflow_name} timed out connecting to Postgres ({target}). Check the "
            f"service, port, and network policy: {timeout}"
        )

    return f"{workflow_name} failed to use Postgres ({target}): {exc}"


def is_database_error(exc: BaseException) -> bool:
    return any(
        isinstance(
            item,
            SQLAlchemyError | gaierror | ConnectionRefusedError | TimeoutError,
        )
        for item in walk_exception_chain(exc)
    )


def database_error_context(
    *,
    database_url: str,
    exc: BaseException,
    workflow_name: str,
    secret_ref: str = "DATABASE_URL",
) -> dict[str, str]:
    return {
        "reason": database_error_message(
            database_url=database_url,
            exc=exc,
            workflow_name=workflow_name,
            secret_ref=secret_ref,
        ),
        "database_target": database_target(database_url),
        "error_type": type(exc).__name__,
    }


def to_database_connection_error(
    *,
    database_url: str,
    exc: BaseException,
    workflow_name: str,
    secret_ref: str = "DATABASE_URL",
) -> DatabaseConnectionError:
    return DatabaseConnectionError(
        database_error_message(
            database_url=database_url,
            exc=exc,
            workflow_name=workflow_name,
            secret_ref=secret_ref,
        )
    )
