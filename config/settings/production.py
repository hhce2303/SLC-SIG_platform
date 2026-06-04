from .base import *  # noqa: F401,F403

DEBUG = False

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# sig_token cookie must be Secure when served over HTTPS
SIGTOOLS_COOKIE_SECURE = True
# SameSite=Lax works because installations.sig.systems and api.sig.systems share the same eTLD+1
SIGTOOLS_COOKIE_SAMESITE = "Lax"
SIGTOOLS_COOKIE_DOMAIN = ".sig.systems"
