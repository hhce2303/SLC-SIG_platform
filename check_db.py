import django
import os
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
django.setup()
from django.db import connections

for alias in ["default", "inventory", "schedules", "sigtools"]:
    try:
        conn = connections[alias]
        conn.ensure_connection()
        h = conn.settings_dict["HOST"]
        p = conn.settings_dict["PORT"]
        n = conn.settings_dict["NAME"]
        print(f"[OK]   {alias}: {h}:{p} / {n}")
    except Exception as e:
        print(f"[FAIL] {alias}: {e}")
