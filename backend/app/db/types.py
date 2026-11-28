"""Timezone-aware timestamp column type.

SQLite (the default local ``DATABASE_URL``) has no native timezone-aware
datetime storage: SQLAlchemy strips ``tzinfo`` on write and returns naive
datetimes on read, so ``created_at`` lost its UTC offset on every
round-trip. The history endpoints then emitted offset-less strings that
the frontend parsed as local time.

``UTCTimestamp`` keeps the round-trip offset-aware on every dialect:

- on bind, naive values are assumed to be UTC (every writer uses
  ``get_utc_now``) and aware values are normalised to UTC;
- on read, naive values coming back from SQLite (including rows written
  before this fix) are re-attached to UTC, and aware values are
  normalised to UTC.

PostgreSQL keeps its native ``timestamptz`` behaviour: the underlying
implementation type is still ``DateTime(timezone=True)``, so the DDL is
unchanged and no migration is needed.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UTCTimestamp(TypeDecorator):
    """DateTime that always round-trips as an aware UTC datetime."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
