from .base import *  # noqa: F401,F403

import environ

env = environ.Env()

if env.bool("READ_DOT_ENV", default=True):
    environ.Env.read_env(BASE_DIR / ".env")

ENVIRONMENT = env("DJANGO_ENV", default="development")

if ENVIRONMENT == "production":
    from .production import *  # noqa: F401,F403
else:
    from .development import *  # noqa: F401,F403
