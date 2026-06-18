from .base import *  # noqa: F401,F403

DEBUG = False

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# sig_token cookie Secure flag.
#
# A `Secure` cookie is only stored/sent by the browser over HTTPS. Production
# currently serves the API over plain HTTP (http://api.sig.systems:8091 — ports
# 80/443 are not reachable yet), so with Secure=True the browser silently DROPS
# the login cookie and every /me/ and /stream/ returns 401.
#
# Default False to match the HTTP-only reality. Once TLS is live on
# api.sig.systems (see docker/HTTPS.md), set SIGTOOLS_COOKIE_SECURE=true in the
# server's .env to harden it — no code change needed.
SIGTOOLS_COOKIE_SECURE = env.bool("SIGTOOLS_COOKIE_SECURE", default=False)
# SameSite=Lax works because installations.sig.systems and api.sig.systems share the same eTLD+1
SIGTOOLS_COOKIE_SAMESITE = "Lax"
SIGTOOLS_COOKIE_DOMAIN = env("SIGTOOLS_COOKIE_DOMAIN", default=".sig.systems")
if SIGTOOLS_COOKIE_DOMAIN == "":
    SIGTOOLS_COOKIE_DOMAIN = None
