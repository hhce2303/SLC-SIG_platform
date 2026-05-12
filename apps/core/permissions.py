from rest_framework.permissions import BasePermission


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
