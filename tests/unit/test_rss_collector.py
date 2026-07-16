from socket import gaierror

from shared.db_errors import (
    database_error_context,
    database_error_message,
    database_target,
    is_database_error,
)


def test_database_target_redacts_credentials() -> None:
    target = database_target(
        "postgresql+asyncpg://mimir:secret@postgres.mimir.svc.cluster.local:5432/mimir"
    )

    assert target == "postgresql+asyncpg://postgres.mimir.svc.cluster.local:5432/mimir"
    assert "secret" not in target
    assert "mimir:secret" not in target


def test_database_error_message_identifies_dns_failures() -> None:
    database_url = "postgresql+asyncpg://mimir:secret@missing-postgres:5432/mimir"
    exc = RuntimeError("outer")
    exc.__cause__ = gaierror(-2, "Name or service not known")

    message = database_error_message(
        database_url=database_url,
        exc=exc,
        workflow_name="RSS collector",
        secret_ref="mimir-db-secret/postgres-url in the argo namespace",
    )

    assert "could not resolve the Postgres host" in message
    assert "missing-postgres:5432/mimir" in message
    assert "mimir:secret" not in message


def test_database_error_message_identifies_refused_connections() -> None:
    database_url = (
        "postgresql+asyncpg://mimir:secret@postgres.mimir.svc.cluster.local:5432/mimir"
    )

    message = database_error_message(
        database_url=database_url,
        exc=ConnectionRefusedError("refused"),
        workflow_name="Health analyze",
        secret_ref="mimir-db-secret/postgres-url in the argo namespace",
    )

    assert "connection was refused" in message
    assert "postgres.mimir.svc.cluster.local:5432/mimir" in message
    assert "secret" not in message


def test_database_error_context_omits_plaintext_password() -> None:
    database_url = (
        "postgresql+asyncpg://mimir:trapsarmadillofemininesimply@"
        "mimir-db-svc:5432/mimir"
    )
    exc = RuntimeError("outer")
    exc.__cause__ = gaierror(-2, "Name or service not known")

    context = database_error_context(
        database_url=database_url,
        exc=exc,
        workflow_name="Health analyze",
        secret_ref="mimir-db-secret/postgres-url in the argo namespace",
    )

    joined = " ".join(context.values())
    assert "trapsarmadillofemininesimply" not in joined
    assert "mimir-db-svc:5432/mimir" in joined
    assert context["error_type"] == "RuntimeError"
    assert is_database_error(exc)
