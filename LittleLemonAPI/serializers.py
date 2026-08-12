"""Serializers for the Little Lemon API."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from .models import Cart, Category, MenuItem, Order, OrderItem
from .permissions import DELIVERY_CREW_GROUP, MANAGER_GROUP

User = get_user_model()


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "slug", "title"]


class MenuItemSerializer(serializers.ModelSerializer):
    """Nested category on read, ``category_id`` on write."""

    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source="category", write_only=True
    )

    class Meta:
        model = MenuItem
        fields = ["id", "title", "price", "featured", "category", "category_id"]

    def validate_price(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("Price must be greater than zero.")
        return value


class ItemOfTheDaySerializer(serializers.Serializer):
    """Write-only payload used by managers to promote a menu item.

    ``PUT /api/menu-items/item-of-the-day/`` with ``{"menuitem": <id>}``.
    """

    menuitem = serializers.PrimaryKeyRelatedField(queryset=MenuItem.objects.all())

    def update_item_of_the_day(self) -> MenuItem:
        item = self.validated_data["menuitem"]
        item.featured = True
        item.save()  # MenuItem.save() demotes the previous item of the day
        return item


class UserSerializer(serializers.ModelSerializer):
    """User representation used by Djoser and by the group-management endpoints."""

    groups = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="name"
    )

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "groups"]
        read_only_fields = ["id", "groups"]


class GroupAssignmentSerializer(serializers.Serializer):
    """Accepts ``{"username": "..."}`` or ``{"user_id": 3}`` to add a user to a group."""

    username = serializers.CharField(required=False)
    user_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        if not attrs.get("username") and not attrs.get("user_id"):
            raise serializers.ValidationError("Provide either 'username' or 'user_id'.")
        lookup = {"username": attrs["username"]} if attrs.get("username") else {"pk": attrs["user_id"]}
        try:
            attrs["user"] = User.objects.get(**lookup)
        except User.DoesNotExist:
            raise serializers.ValidationError("No such user.")
        return attrs


class CartSerializer(serializers.ModelSerializer):
    """Cart line. Money fields are computed server-side from the live menu price."""

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    menuitem = serializers.PrimaryKeyRelatedField(queryset=MenuItem.objects.all())
    menuitem_detail = MenuItemSerializer(source="menuitem", read_only=True)

    class Meta:
        model = Cart
        fields = ["id", "user", "menuitem", "menuitem_detail", "quantity", "unit_price", "price"]
        read_only_fields = ["unit_price", "price"]
        validators = [
            UniqueTogetherValidator(
                queryset=Cart.objects.all(),
                fields=["user", "menuitem"],
                message="This item is already in your cart; update its quantity instead.",
            )
        ]


class OrderItemSerializer(serializers.ModelSerializer):
    menuitem_detail = MenuItemSerializer(source="menuitem", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "menuitem", "menuitem_detail", "quantity", "unit_price", "price"]
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    """Read representation of an order, including its frozen line items."""

    items = OrderItemSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    delivery_crew = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Order
        fields = ["id", "user", "delivery_crew", "status", "total", "date", "items"]
        read_only_fields = fields


class OrderUpdateSerializer(serializers.ModelSerializer):
    """Write path for orders.

    Managers may assign a delivery crew member and flip the status; the delivery
    crew may only flip the status of orders assigned to them. Field-level
    stripping happens in :meth:`validate`, driven by the requesting user's role.
    """

    delivery_crew = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(groups__name=DELIVERY_CREW_GROUP),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Order
        fields = ["id", "delivery_crew", "status"]

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        is_crew = user.groups.filter(name=DELIVERY_CREW_GROUP).exists()
        is_mgr = user.is_staff or user.groups.filter(name=MANAGER_GROUP).exists()

        if is_mgr:
            return attrs
        if is_crew:
            # Delivery crew touch nothing but the delivery status.
            if set(attrs) - {"status"}:
                raise serializers.ValidationError(
                    "The delivery crew may only update the order status."
                )
            return attrs
        raise serializers.ValidationError("You are not allowed to update orders.")
