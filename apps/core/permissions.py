from rest_framework.permissions import BasePermission


def has_app_permission(user, perm_key: str) -> bool:
    """
    Checks if *user* holds a specific AppPermission key via the sigtools_beta
    user_app_roles → role_permissions → app_permissions chain.

    Works for SigtoolsWebUser (cookie-authenticated) only; returns False for
    all other user types so daily-log JWT users are denied by default.
    """
    from apps.sigtools_auth.authentication import SigtoolsWebUser  # local to avoid circular

    if not isinstance(user, SigtoolsWebUser):
        return False

    from django.db import connections

    sql = """
        SELECT COUNT(*)
        FROM app_permissions p
        JOIN role_permissions rp  ON rp.permission_id = p.id
        JOIN user_app_roles   uar ON uar.role_id       = rp.role_id
        WHERE uar.user_id = %s AND p.key = %s
    """
    try:
        with connections["sigtools"].cursor() as cur:
            cur.execute(sql, [user.id, perm_key])
            return cur.fetchone()[0] > 0
    except Exception:
        return False


class _RolePermission(BasePermission):
    """Base class for role-based permissions. Subclass and set `allowed_roles`."""

    allowed_roles: tuple[str, ...] = ()

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "daily_user", None)
        if user is None:
            return False
        role_name = getattr(user, "_role_name", None)
        if role_name is None:
            try:
                role_name = user.role.name
            except Exception:
                return False
            user._role_name = role_name
        return role_name in self.allowed_roles


class IsAdmin(_RolePermission):
    allowed_roles = ("Admin",)
    message = "Only administrators can perform this action."


class IsSupervisor(_RolePermission):
    allowed_roles = ("Supervisor", "Lead Supervisor", "Admin")
    message = "Supervisor access required."


class IsLeadSupervisor(_RolePermission):
    allowed_roles = ("Lead Supervisor", "Admin")
    message = "Lead Supervisor access required."


class IsOperator(_RolePermission):
    allowed_roles = ("Operador",)
    message = "Operator access required."


class IsOperatorOrReadOnly(BasePermission):
    """Operators can write; others can only read."""

    def has_permission(self, request, view) -> bool:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = getattr(request, "daily_user", None)
        if user is None:
            return False
        try:
            return user.role.name == "Operador"
        except Exception:
            return False
