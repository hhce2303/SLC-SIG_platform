import uuid
from django.db import connections

sql = "INSERT IGNORE INTO permissions (id, `key`, label, description, app, category) VALUES (%s, %s, %s, %s, %s, %s)"

rows = [
    (str(uuid.uuid4()), "installations.sites.view",         "Ver sitios",        "Acceder al listado de sitios de instalacion", "installations", "Infrastructure"),
    (str(uuid.uuid4()), "installations.installations.view", "Ver instalaciones", "Acceder al modulo de instalaciones",          "installations", "Infrastructure"),
]

with connections["sigtools"].cursor() as cur:
    for row in rows:
        cur.execute(sql, row)
        status = "inserted" if cur.rowcount else "already exists"
        print(status, row[1])
