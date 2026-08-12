"""Custom role-based permissions.

Roles are Django auth groups: ``Manager`` and ``Delivery crew``. Anything else
authenticated is a customer; superusers/staff are admins.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

MANAGER_GROUP = "Manager"
DELIVERY_CREW_GROUP = "Delivery crew"


def in_group(user, name: str) -> bool:
    """True when ``user`` is authenticated and belongs to the named group."""
    return bool(user and user.is_authenticated and user.groups.filter(name=name).exists())


def is_manager(user) -> bool:
    """Managers, plus admins who implicitly hold every role."""
    return bool(user and user.is_authenticated and (user.is_staff or in_group(user, MANAGER_GROUP)))


def is_delivery_crew(user) -> bool:
    return in_group(user, DELIVERY_CREW_GROUP)


class IsAdmin(BasePermission):
    """Superuser / staff only."""

    message = "Admin privileges are required for this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsManager(BasePermission):
    """Members of the Manager group (admins included)."""

    message = "Manager privileges are required for this action."

    def has_permission(self, request, view):
        return is_manager(request.user)


class IsDeliveryCrew(BasePermission):
    """Members of the Delivery crew group."""

    message = "Delivery crew privileges are required for this action."

    def has_permission(self, request, view):
        return is_delivery_crew(request.user)


class IsCustomer(BasePermission):
    """Authenticated users holding no staff role — the ordering customers."""

    message = "Only customers can use this endpoint."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and not user.is_staff
            and not in_group(user, MANAGER_GROUP)
            and not is_delivery_crew(user)
        )


class ReadOnly(BasePermission):
    """Grants GET/HEAD/OPTIONS to any authenticated user."""

    def has_permission(self, request, view):
        return bool(
            request.method in SAFE_METHODS and request.user and request.user.is_authenticated
        )


class IsAdminOrReadOnly(BasePermission):
    """Everyone authenticated may read; only admins may write.

    Used for categories and the menu-item catalogue.
    """

    message = "Only administrators can modify the menu."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsManagerOrAdminOrReadOnly(BasePermission):
    """Read for all authenticated users; writes for managers and admins.

    Menu items accept manager writes so managers can flip the item of the day.
    The serializer restricts *which* fields a plain manager may change.
    """

    message = "Only managers or administrators can modify this resource."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return is_manager(request.user)
