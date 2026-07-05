from sqlalchemy import inspect, text

from extensions import db


def apply_compatible_schema_updates() -> None:
    inspector = inspect(db.engine)
    if "users" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    statements = []
    if "phone_number" not in columns:
        statements.append("ALTER TABLE users ADD COLUMN phone_number VARCHAR(32)")
    if "phone_confirmed_at" not in columns:
        statements.append("ALTER TABLE users ADD COLUMN phone_confirmed_at TIMESTAMP")
    for statement in statements:
        db.session.execute(text(statement))
    if statements:
        db.session.commit()
