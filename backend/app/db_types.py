"""
Cross-dialect column types.

Postgres uses native UUID / JSONB / ARRAY. SQLite (used in tests) doesn't
have these, so we fall back to portable equivalents. This lets the same
models run against both engines without change.
"""
import uuid
import json
from sqlalchemy.types import TypeDecorator, CHAR, TEXT
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB as PG_JSONB, ARRAY as PG_ARRAY


class GUID(TypeDecorator):
    """Platform-independent UUID type (native on Postgres, CHAR(36) elsewhere)."""
    impl = CHAR
    cache_ok = True

    def __init__(self, as_uuid=True, *args, **kwargs):
        # `as_uuid` accepted for drop-in compatibility with postgresql.UUID
        self.as_uuid = as_uuid
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(value)
        return value


class JSONB(TypeDecorator):
    """JSONB on Postgres, JSON-encoded TEXT elsewhere."""
    impl = TEXT
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_JSONB())
        return dialect.type_descriptor(TEXT())

    def process_bind_param(self, value, dialect):
        if dialect.name == "postgresql" or value is None:
            return value
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if dialect.name == "postgresql" or value is None:
            return value
        return json.loads(value)


class ARRAY(TypeDecorator):
    """ARRAY(String) on Postgres, JSON-encoded TEXT elsewhere."""
    impl = TEXT
    cache_ok = True

    def __init__(self, item_type=None, *args, **kwargs):
        self.item_type = item_type
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_ARRAY(self.item_type))
        return dialect.type_descriptor(TEXT())

    def process_bind_param(self, value, dialect):
        if dialect.name == "postgresql" or value is None:
            return value
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if dialect.name == "postgresql" or value is None:
            return value
        return json.loads(value)
