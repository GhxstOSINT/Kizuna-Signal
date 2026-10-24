from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

T = TypeVar("T")


def create_once(
    db: Session,
    model: type[T],
    scope: dict[str, Any],
    key: str | None,
    build: Callable[[], T],
) -> tuple[T, bool]:
    """Create via `build()` unless `key` was already used within `scope`.

    Returns (row, created). A repeated key returns the original row, so retried
    requests never duplicate work. Concurrent duplicates are caught by the
    unique constraint on (scope, idempotency_key).
    """

    def existing() -> T | None:
        if key is None:
            return None
        return db.scalar(select(model).filter_by(idempotency_key=key, **scope))

    if (row := existing()) is not None:
        return row, False
    obj = build()
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if (row := existing()) is not None:
            return row, False
        raise
    db.refresh(obj)
    return obj, True
