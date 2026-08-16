"""Serializers for the Little Lemon capstone API."""
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Booking, Menu

User = get_user_model()


class MenuSerializer(serializers.ModelSerializer):
    """Full representation of a menu item."""

    class Meta:
        model = Menu
        fields = ["id", "title", "price", "inventory"]


class BookingSerializer(serializers.ModelSerializer):
    """A table reservation.

    ``user`` is read-only: the owner is taken from the authenticated request in
    the view, never from client input, so a caller cannot book on behalf of
    someone else.
    """

    class Meta:
        model = Booking
        fields = ["id", "user", "name", "no_of_guests", "booking_date"]
        read_only_fields = ["user"]


class UserSerializer(serializers.ModelSerializer):
    """Read-only user profile returned by the Djoser endpoints."""

    class Meta:
        model = User
        fields = ["id", "username", "email"]
        read_only_fields = ["id"]
