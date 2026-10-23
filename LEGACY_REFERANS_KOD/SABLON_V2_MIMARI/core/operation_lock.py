import sqlite3
import time
import uuid
from contextlib import contextmanager

from core.db import get_db_connection


class TemplateBusyError(RuntimeError):
    """Raised when the same template is already owned by another operation."""


def acquire_template_lock(
    category: str,
    template: str,
    operation: str,
    *,
    wait_seconds: float = 0.0,
    lease_seconds: float = 900.0,
) -> str:
    category = str(category or "").strip()
    template = str(template or "").strip()
    operation = str(operation or "operation").strip()
    if not category or not template:
        raise ValueError("Kategori/şablon kilidi için isimler gerekli.")

    owner_token = uuid.uuid4().hex
    deadline = time.monotonic() + max(0.0, float(wait_seconds))

    while True:
        now = time.time()
        conn = get_db_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "DELETE FROM template_operation_locks "
                "WHERE expires_epoch<=?",
                (now,),
            )
            try:
                conn.execute(
                    """INSERT INTO template_operation_locks (
                           category, template, owner_token, operation,
                           acquired_epoch, expires_epoch
                       ) VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        category,
                        template,
                        owner_token,
                        operation,
                        now,
                        now + max(30.0, float(lease_seconds)),
                    ),
                )
                conn.commit()
                return owner_token
            except sqlite3.IntegrityError:
                row = conn.execute(
                    """SELECT operation
                       FROM template_operation_locks
                       WHERE category=? AND template=?""",
                    (category, template),
                ).fetchone()
                conn.rollback()
                busy_operation = (
                    str(row["operation"])
                    if row is not None
                    else "başka bir işlem"
                )
        finally:
            conn.close()

        if time.monotonic() >= deadline:
            raise TemplateBusyError(
                f"{category}/{template} şu anda '{busy_operation}' "
                "işlemi tarafından kullanılıyor. Birkaç saniye sonra tekrar deneyin."
            )
        time.sleep(0.08)


def release_template_lock(
    category: str,
    template: str,
    owner_token: str,
) -> None:
    conn = get_db_connection()
    try:
        conn.execute(
            """DELETE FROM template_operation_locks
               WHERE category=? AND template=? AND owner_token=?""",
            (str(category), str(template), str(owner_token)),
        )
        conn.commit()
    finally:
        conn.close()


@contextmanager
def template_operation_lock(
    category: str,
    template: str,
    operation: str,
    *,
    wait_seconds: float = 0.0,
    lease_seconds: float = 900.0,
):
    token = acquire_template_lock(
        category,
        template,
        operation,
        wait_seconds=wait_seconds,
        lease_seconds=lease_seconds,
    )
    try:
        yield token
    finally:
        release_template_lock(category, template, token)
