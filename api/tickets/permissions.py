from rest_framework.permissions import BasePermission, SAFE_METHODS


class TicketRolePermission(BasePermission):
    """Enforce ticket permissions using the user's Django groups and model perms."""

    message = "Your role does not allow this ticket action."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            permission = "tickets.view_ticket"
        elif request.method == "POST":
            permission = "tickets.add_ticket"
        elif request.method in {"PUT", "PATCH", "DELETE"}:
            permission = "tickets.change_ticket"
        else:
            return False

        return user.has_perm(permission)
