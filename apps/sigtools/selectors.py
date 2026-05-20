"""Read-only queries for sigtools (sites, cameras, etc.)."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            os.environ["SIGTOOLS_SQLALCHEMY_URL"],
            pool_size=2,
            max_overflow=0,
            pool_recycle=1800,
            pool_pre_ping=True,
        )
    return _engine


def get_all_sites() -> list[dict]:
    """Obtiene todos los sitios: id, name, cameras_count."""
    with _get_engine().connect() as conn:
        rows = conn.execute(
            text("SELECT id, name, cameras_count FROM sites ORDER BY id ASC")
        ).fetchall()
        return [{"id": r[0], "name": r[1], "cameras_count": r[2]} for r in rows]


def get_site_by_id(site_id: int) -> dict | None:
    """Obtiene un sitio por ID."""
    with _get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT id, name FROM sites WHERE id = :site_id"),
            {"site_id": site_id},
        ).fetchone()
        return {"id": row[0], "name": row[1]} if row else None
