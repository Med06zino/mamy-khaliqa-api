from rest_framework.permissions import BasePermission


class IsStaffUser(BasePermission):
    """Acces reserve a l'administration (is_staff)."""

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_active and u.is_staff)
