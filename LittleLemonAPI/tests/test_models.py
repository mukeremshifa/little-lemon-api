"""Model-level tests: string representations and field validation."""
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from LittleLemonAPI.models import Booking, Menu

User = get_user_model()


class MenuModelTest(TestCase):
    def test_str_renders_title_and_price(self):
        item = Menu.objects.create(title="Ice Cream", price=Decimal("8.00"), inventory=100)
        self.assertEqual(str(item), "Ice Cream : 8.00")

    def test_negative_price_is_rejected(self):
        item = Menu(title="Bad Deal", price=Decimal("-1.00"), inventory=1)
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_items_are_ordered_by_title(self):
        Menu.objects.create(title="Zucchini Fries", price=Decimal("6.00"), inventory=5)
        Menu.objects.create(title="Apple Tart", price=Decimal("7.50"), inventory=5)
        self.assertEqual(
            list(Menu.objects.values_list("title", flat=True)),
            ["Apple Tart", "Zucchini Fries"],
        )


class BookingModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="diner", password="CapstonePass123!")
        self.when = datetime(2026, 9, 1, 19, 30, tzinfo=dt_timezone.utc)

    def test_str_includes_name_and_guest_count(self):
        booking = Booking.objects.create(
            user=self.user, name="Mukerem", no_of_guests=4, booking_date=self.when
        )
        self.assertIn("Mukerem", str(booking))
        self.assertIn("4 guests", str(booking))

    def test_guest_count_below_one_is_rejected(self):
        booking = Booking(user=self.user, name="Nobody", no_of_guests=0, booking_date=self.when)
        with self.assertRaises(ValidationError):
            booking.full_clean()

    def test_booking_without_user_is_allowed(self):
        """Admin-created bookings have no request user attached."""
        booking = Booking.objects.create(name="Walk-in", no_of_guests=2, booking_date=self.when)
        self.assertIsNone(booking.user)

    def test_bookings_are_ordered_by_date(self):
        later = datetime(2026, 9, 2, 20, 0, tzinfo=dt_timezone.utc)
        Booking.objects.create(user=self.user, name="Second", no_of_guests=2, booking_date=later)
        Booking.objects.create(user=self.user, name="First", no_of_guests=2, booking_date=self.when)
        self.assertEqual(
            list(Booking.objects.values_list("name", flat=True)), ["First", "Second"]
        )
