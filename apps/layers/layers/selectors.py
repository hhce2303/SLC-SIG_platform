"""Selectors (lecturas) para layers."""

from django.db import connections


def get_all_layers():
    """Obtiene todos los layers de la tabla layers en sigtools.
    
    Returns:
        list: Lista de dicts con {id, name}
    """
    with connections["sigtools"].cursor() as cur:
        cur.execute("SELECT id, name FROM layers")
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
