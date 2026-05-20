"""SQLAlchemy schema introspection — read-only, used to build Claude context."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, inspect


def get_schema_context(table_names: list[str] | None = None) -> dict:
    """
    Inspects the MySQL DB and returns a structured dict with column/FK/index info.
    Used as context for Claude's prompt engineering step — NOT for the generated code.

    Args:
        table_names: Optional list of tables to inspect. Inspects all if None.

    Returns:
        {
            "table_name": {
                "columns": [{"name": ..., "type": ..., "nullable": ...}],
                "foreign_keys": [{"columns": [...], "references": "table.col"}],
                "indexes": [["col1", "col2"]],
            }
        }
    """
    engine = create_engine(
        os.environ["SQLALCHEMY_DATABASE_URL"],
        pool_size=2,
        max_overflow=0,
        pool_recycle=1800,
        pool_pre_ping=True,
    )
    try:
        inspector = inspect(engine)
        tables = table_names or inspector.get_table_names()
        schema: dict = {}

        for table in tables:
            try:
                schema[table] = {
                    "columns": [
                        {
                            "name": col["name"],
                            "type": str(col["type"]),
                            "nullable": col["nullable"],
                        }
                        for col in inspector.get_columns(table)
                    ],
                    "foreign_keys": [
                        {
                            "columns": fk["constrained_columns"],
                            "references": f"{fk['referred_table']}.{fk['referred_columns']}",
                        }
                        for fk in inspector.get_foreign_keys(table)
                    ],
                    "indexes": [
                        idx["column_names"]
                        for idx in inspector.get_indexes(table)
                    ],
                }
            except Exception:
                # Skip tables that can't be inspected (views, missing perms)
                continue

        return schema
    finally:
        engine.dispose()
