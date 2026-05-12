"""
LDAP authentication against sig.com Active Directory.
Mirrors the logic of SIGDesk's app/Helpers/LDAP.php.

Groups are checked in priority order; the first match wins and determines
the access_level returned alongside the user's display name.
"""
from __future__ import annotations

import os

from django.conf import settings

# ---------------------------------------------------------------------------
# Configuration (read from settings / env)
# ---------------------------------------------------------------------------

def _cfg(key: str, default: str) -> str:
    return getattr(settings, key, os.getenv(key, default))


LDAP_HOST = lambda: _cfg("LDAP_HOST", "sig")
LDAP_DOMAIN = lambda: _cfg("LDAP_DOMAIN", "sig.com")
LDAP_BASE_DN = lambda: _cfg("LDAP_BASE_DN", "OU=OU User,DC=sig,DC=com")

# AD groups in priority order — same as LDAP.php
# (group_cn, access_level)
LDAP_GROUPS: list[tuple[str, int]] = [
    ("SIG ITTools",                    1),
    ("SIG ITTools CS",                 2),
    ("SIG ITTools Full Viewer",        3),
    ("SIG ITTools Projects_Services",  4),
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_dn(conn, sam_account_name: str, base_dn: str) -> str:
    """Search for the distinguishedName of an object by sAMAccountName."""
    from ldap3 import SUBTREE
    conn.search(
        search_base=base_dn,
        search_filter=f"(sAMAccountName={sam_account_name})",
        search_scope=SUBTREE,
        attributes=["distinguishedName"],
    )
    if conn.entries:
        return conn.entries[0].entry_dn
    return ""


def _check_group_recursive(conn, user_dn: str, group_dn: str, visited: set | None = None) -> bool:
    """
    Recursively checks if user_dn is a member of group_dn (transitive).
    Replicates checkGroupEx() from LDAP.php.
    """
    from ldap3 import SUBTREE
    if visited is None:
        visited = set()
    if user_dn in visited:
        return False
    visited.add(user_dn)

    conn.search(
        search_base=user_dn,
        search_filter="(objectClass=*)",
        search_scope=SUBTREE,
        attributes=["memberOf"],
    )

    if not conn.entries:
        return False

    member_of = (
        conn.entries[0]["memberOf"].values
        if "memberOf" in conn.entries[0]
        else []
    )

    for parent_dn in member_of:
        if parent_dn.lower() == group_dn.lower():
            return True
        # Recurse into the parent group
        if _check_group_recursive(conn, parent_dn, group_dn, visited):
            return True

    return False


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def ldap_authenticate(username: str, password: str) -> dict:
    """
    Authenticates against the AD and returns:
    {
        "success": bool,
        "ldap_response": int,    # access_level (1–4) on success, 0 on failure
        "display_name": str,     # CN from AD on success, "" on failure
        "message": str           # error message if success=False
    }
    """
    try:
        from ldap3 import ALL, Connection, Server
        from ldap3.core.exceptions import LDAPBindError, LDAPException
    except ImportError:
        return {
            "success": False,
            "ldap_response": 0,
            "display_name": "",
            "message": "ldap3 is not installed.",
        }

    domain = LDAP_DOMAIN()
    host = LDAP_HOST()
    base_dn = LDAP_BASE_DN()

    server = Server(f"ldap://{domain}", get_info=ALL)

    try:
        conn = Connection(
            server,
            user=f"{username}@{domain}",
            password=password,
            auto_bind=True,
        )
    except LDAPBindError:
        return {
            "success": False,
            "ldap_response": 0,
            "display_name": "",
            "message": "Invalid credentials.",
        }
    except LDAPException as exc:
        return {
            "success": False,
            "ldap_response": 0,
            "display_name": "",
            "message": f"LDAP error: {exc}",
        }

    user_dn = _get_dn(conn, username, base_dn)
    if not user_dn:
        conn.unbind()
        return {
            "success": False,
            "ldap_response": 0,
            "display_name": "",
            "message": "User not found in directory.",
        }

    # Extract display name from DN  (CN=Juan Cruz,OU=... → "Juan Cruz")
    first_part = user_dn.split(",")[0]
    display_name = first_part.split("=", 1)[1] if "=" in first_part else username

    for group_cn, level in LDAP_GROUPS:
        group_dn = _get_dn(conn, group_cn, base_dn)
        if group_dn and _check_group_recursive(conn, user_dn, group_dn):
            conn.unbind()
            return {
                "success": True,
                "ldap_response": level,
                "display_name": display_name,
                "message": "",
            }

    conn.unbind()
    return {
        "success": False,
        "ldap_response": 0,
        "display_name": "",
        "message": "You are not authorized to access this area.",
    }
