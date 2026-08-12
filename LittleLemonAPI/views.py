"""API views for the Little Lemon restaurant.

Endpoint map (all paths are prefixed with ``/api/``)::

    users/                          POST   register a customer            (Djoser)
    users/me/                       GET    current profile                (Djoser)
    token/login/                    POST   obtain an auth token           (Djoser)

    categories/                     GET    browse    | POST   admin
    categories/<pk>/                GET    retrieve  | PUT/PATCH/DELETE admin
    menu-items/                     GET    browse (filter/sort/paginate) | POST admin
    menu-items/<pk>/                GET    retrieve | PATCH manager (featured only) / admin
    menu-items/item-of-the-day/     GET    current featured item | PUT manager

    groups/manager/users/           GET/POST admin        | DELETE /<pk>/
    groups/delivery-crew/users/     GET/POST manager      | DELETE /<pk>/

    cart/menu-items/                GET/POST/DELETE  the caller's own cart
    orders/                         GET role-scoped list | POST place order from cart
    orders/<pk>/                    GET | PATCH (manager/crew) | DELETE (manager)
"""
from decimal import Decimal

import django_filters
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Cart, Category, MenuItem, Order, OrderItem
from .permissions import (
    DELIVERY_CREW_GROUP,
    MANAGER_GROUP,
    IsAdmin,
    IsAdminOrReadOnly,
    IsManager,
    is_delivery_crew,
    is_manager,
)
from .serializers import (
    CartSerializer,
    CategorySerializer,
    GroupAssignmentSerializer,
    ItemOfTheDaySerializer,
    MenuItemSerializer,
    OrderSerializer,
    OrderUpdateSerializer,
    UserSerializer,
)

User = get_user_model()


# --------------------------------------------------------------------------- #
# Categories                                             (criteria 4, 13)
# --------------------------------------------------------------------------- #
class CategoriesView(generics.ListCreateAPIView):
    """GET: any authenticated user browses categories. POST: admin only."""

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    ordering_fields = ["title", "slug"]
    search_fields = ["title", "slug"]


class SingleCategoryView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]


# --------------------------------------------------------------------------- #
# Menu items                              (criteria 3, 6, 14, 15, 16, 17)
# --------------------------------------------------------------------------- #
class MenuItemFilter(django_filters.FilterSet):
    """``?category=`` accepts a category id, slug, or title (case-insensitive)."""

    category = django_filters.CharFilter(method="filter_category")
    price_min = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    price_max = django_filters.NumberFilter(field_name="price", lookup_expr="lte")

    class Meta:
        model = MenuItem
        fields = ["category", "featured", "price_min", "price_max"]

    def filter_category(self, queryset, name, value):
        lookup = Q(category__slug__iexact=value) | Q(category__title__iexact=value)
        if value.isdigit():
            lookup |= Q(category_id=int(value))
        return queryset.filter(lookup)


class MenuItemsView(generics.ListCreateAPIView):
    """Browse the menu with filtering, sorting and pagination; admins may add items.

    Examples::

        GET /api/menu-items/?ordering=price          # cheapest first   (criterion 17)
        GET /api/menu-items/?ordering=-price
        GET /api/menu-items/?category=desserts       # by category      (criterion 15)
        GET /api/menu-items/?page=2&perpage=5        # pagination       (criterion 16)
        GET /api/menu-items/?search=lemon
    """

    queryset = MenuItem.objects.select_related("category").all()
    serializer_class = MenuItemSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_class = MenuItemFilter
    ordering_fields = ["price", "title"]
    ordering = ["title"]
    search_fields = ["title", "category__title"]

    def paginate_queryset(self, queryset):
        # Allow the client to size the page via ?perpage= (capped) on top of ?page=.
        perpage = self.request.query_params.get("perpage")
        if perpage and perpage.isdigit():
            self.paginator.page_size = min(int(perpage), 100)
        return super().paginate_queryset(queryset)


class SingleMenuItemView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve for everyone; admins edit freely, managers may only flip ``featured``."""

    queryset = MenuItem.objects.select_related("category").all()
    serializer_class = MenuItemSerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated()]
        if self.request.method == "PATCH":
            # Managers reach PATCH so they can set the item of the day.
            return [IsManager()]
        return [IsAdmin()]

    def update(self, request, *args, **kwargs):
        if not request.user.is_staff and set(request.data) - {"featured"}:
            return Response(
                {"detail": "Managers may only update the 'featured' (item of the day) field."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)


class ItemOfTheDayView(APIView):
    """The current item of the day.

    GET  -> the featured menu item (``null`` when none is set).
    PUT  -> ``{"menuitem": <id>}`` promotes that item; managers and admins only.
    """

    def get_permissions(self):
        return [IsAuthenticated()] if self.request.method == "GET" else [IsManager()]

    def get(self, request):
        item = MenuItem.objects.select_related("category").filter(featured=True).first()
        if item is None:
            return Response({"item_of_the_day": None})
        return Response(MenuItemSerializer(item).data)

    def put(self, request):
        serializer = ItemOfTheDaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.update_item_of_the_day()
        return Response(MenuItemSerializer(item).data, status=status.HTTP_200_OK)

    # PATCH behaves identically to PUT for this single-field resource.
    patch = put


# --------------------------------------------------------------------------- #
# Group management                                    (criteria 1, 2, 7)
# --------------------------------------------------------------------------- #
class BaseGroupUsersView(APIView):
    """List the members of a role group, and add users to it."""

    group_name = ""

    def _group(self):
        group, _ = Group.objects.get_or_create(name=self.group_name)
        return group

    def get(self, request):
        users = User.objects.filter(groups__name=self.group_name).order_by("username")
        return Response(UserSerializer(users, many=True).data)

    def post(self, request):
        serializer = GroupAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.groups.add(self._group())
        return Response(
            {"message": f"{user.username} added to {self.group_name}."},
            status=status.HTTP_201_CREATED,
        )


class BaseSingleGroupUserView(APIView):
    """Remove one user from a role group."""

    group_name = ""

    def delete(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        group = get_object_or_404(Group, name=self.group_name)
        if not user.groups.filter(pk=group.pk).exists():
            return Response(
                {"detail": f"{user.username} is not in {self.group_name}."},
                status=status.HTTP_404_NOT_FOUND,
            )
        user.groups.remove(group)
        return Response(
            {"message": f"{user.username} removed from {self.group_name}."},
            status=status.HTTP_200_OK,
        )


class ManagerUsersView(BaseGroupUsersView):
    """Admin-only management of the Manager group (criteria 1 & 2)."""

    permission_classes = [IsAdmin]
    group_name = MANAGER_GROUP


class SingleManagerUserView(BaseSingleGroupUserView):
    permission_classes = [IsAdmin]
    group_name = MANAGER_GROUP


class DeliveryCrewUsersView(BaseGroupUsersView):
    """Managers (and admins) staff the delivery crew (criterion 7)."""

    permission_classes = [IsManager]
    group_name = DELIVERY_CREW_GROUP


class SingleDeliveryCrewUserView(BaseSingleGroupUserView):
    permission_classes = [IsManager]
    group_name = DELIVERY_CREW_GROUP


# --------------------------------------------------------------------------- #
# Cart                                                  (criteria 18, 19)
# --------------------------------------------------------------------------- #
class CartView(generics.ListCreateAPIView, generics.DestroyAPIView):
    """The requesting user's own cart.

    GET    -> current cart lines                        (criterion 19)
    POST   -> add ``{"menuitem": id, "quantity": n}``   (criterion 18)
    DELETE -> empty the cart, or ``?menuitem=<id>`` to drop a single line
    """

    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return Cart.objects.select_related("menuitem", "menuitem__category").filter(
            user=self.request.user
        )

    def delete(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        menuitem = request.query_params.get("menuitem")
        if menuitem:
            queryset = queryset.filter(menuitem_id=menuitem)
        deleted, _ = queryset.delete()
        return Response({"deleted": deleted}, status=status.HTTP_200_OK)


# --------------------------------------------------------------------------- #
# Orders                                     (criteria 8, 9, 10, 20, 21)
# --------------------------------------------------------------------------- #
class OrdersView(generics.ListCreateAPIView):
    """Role-scoped order list, and order placement.

    GET  -> customers see their own orders (criterion 21), the delivery crew sees
            orders assigned to them (criterion 9), managers/admins see everything.
    POST -> converts the caller's cart into an order and empties the cart
            (criterion 20).
    """

    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "delivery_crew"]
    ordering_fields = ["date", "total", "id"]
    ordering = ["-date", "-id"]

    def get_queryset(self):
        user = self.request.user
        qs = Order.objects.prefetch_related("items__menuitem").select_related(
            "user", "delivery_crew"
        )
        if is_manager(user):
            return qs
        if is_delivery_crew(user):
            return qs.filter(delivery_crew=user)
        return qs.filter(user=user)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        cart_items = list(Cart.objects.select_related("menuitem").filter(user=request.user))
        if not cart_items:
            return Response(
                {"detail": "Your cart is empty."}, status=status.HTTP_400_BAD_REQUEST
            )

        total = sum((item.price for item in cart_items), Decimal("0.00"))
        order = Order.objects.create(user=request.user, total=total)
        OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    menuitem=item.menuitem,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    price=item.price,
                )
                for item in cart_items
            ]
        )
        # The cart is consumed by the order.
        Cart.objects.filter(user=request.user).delete()

        return Response(
            OrderSerializer(order).data, status=status.HTTP_201_CREATED
        )


class SingleOrderView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a single order.

    Managers assign a delivery crew member and may flip the status (criterion 8);
    the delivery crew marks their own orders delivered (criterion 10); customers
    have read-only access to their own orders.
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return OrderUpdateSerializer
        return OrderSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Order.objects.prefetch_related("items__menuitem").select_related(
            "user", "delivery_crew"
        )
        if is_manager(user):
            return qs
        if is_delivery_crew(user):
            return qs.filter(delivery_crew=user)
        return qs.filter(user=user)

    def update(self, request, *args, **kwargs):
        if not (is_manager(request.user) or is_delivery_crew(request.user)):
            return Response(
                {"detail": "Only managers or the delivery crew can update orders."},
                status=status.HTTP_403_FORBIDDEN,
            )
        super().update(request, *args, **kwargs)
        # Respond with the full order representation rather than the write payload.
        return Response(OrderSerializer(self.get_object()).data)

    def destroy(self, request, *args, **kwargs):
        if not is_manager(request.user):
            return Response(
                {"detail": "Only managers can delete orders."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)


# --------------------------------------------------------------------------- #
# Convenience
# --------------------------------------------------------------------------- #
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def whoami(request):
    """Report the caller's identity and effective role — handy while testing."""
    user = request.user
    return Response(
        {
            "id": user.id,
            "username": user.username,
            "is_admin": user.is_staff,
            "is_manager": is_manager(user),
            "is_delivery_crew": is_delivery_crew(user),
            "groups": list(user.groups.values_list("name", flat=True)),
        }
    )
