"""Data models for the Little Lemon capstone project."""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Menu(models.Model):
    """A single dish on the restaurant menu."""

    title = models.CharField(max_length=255, db_index=True)
    price = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    inventory = models.SmallIntegerField(
        default=0, validators=[MinValueValidator(0)]
    )

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return f"{self.title} : {self.price}"


class Booking(models.Model):
    """A reserved table.

    ``user`` scopes each reservation to the customer who made it, so the booking
    API can show a caller their own bookings and nothing else. It is nullable so
    bookings created in the Django admin (which have no request user) still work.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)
    no_of_guests = models.SmallIntegerField(validators=[MinValueValidator(1)])
    booking_date = models.DateTimeField()

    class Meta:
        ordering = ["booking_date"]

    def __str__(self) -> str:
        return f"{self.name} - {self.no_of_guests} guests on {self.booking_date}"
