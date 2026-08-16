"""View-level tests for the menu API, the secured booking API, and the HTML routes."""
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from LittleLemonAPI.models import Booking, Menu

User = get_user_model()


def results_of(response):
    """Unwrap a paginated DRF list response."""
    payload = response.json()
    return payload["results"] if isinstance(payload, dict) and "results" in payload else payload


class MenuViewTest(APITestCase):
    """The menu is public to read and requires authentication to modify."""

    def setUp(self):
        self.items = [
            Menu.objects.create(title="Greek Salad", price=Decimal("10.00"), inventory=12),
            Menu.objects.create(title="Lemon Dessert", price=Decimal("8.50"), inventory=20),
            Menu.objects.create(title="Bruschetta", price=Decimal("7.25"), inventory=15),
        ]
        self.user = User.objects.create_user(username="chef", password="CapstonePass123!")
        self.token = Token.objects.create(user=self.user)

    def test_getall_returns_every_menu_item(self):
        response = self.client.get(reverse("menu-items"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results_of(response)), len(self.items))

    def test_retrieve_single_item(self):
        response = self.client.get(reverse("menu-item-detail", args=[self.items[0].id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["title"], "Greek Salad")

    def test_anonymous_cannot_create_menu_item(self):
        response = self.client.post(
            reverse("menu-items"), {"title": "Sneaky", "price": "1.00", "inventory": 1}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Menu.objects.count(), len(self.items))

    def test_authenticated_user_can_create_menu_item(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.post(
            reverse("menu-items"), {"title": "Pasta", "price": "12.00", "inventory": 8}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Menu.objects.filter(title="Pasta").exists())


class BookingViewTest(APITestCase):
    """Every booking endpoint requires a token, and callers are scoped to their own rows."""

    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="CapstonePass123!")
        self.bob = User.objects.create_user(username="bob", password="CapstonePass123!")
        self.alice_token = Token.objects.create(user=self.alice)
        self.bob_token = Token.objects.create(user=self.bob)

        self.when = datetime(2026, 9, 1, 19, 30, tzinfo=dt_timezone.utc)
        self.alice_booking = Booking.objects.create(
            user=self.alice, name="Alice", no_of_guests=2, booking_date=self.when
        )
        self.bob_booking = Booking.objects.create(
            user=self.bob, name="Bob", no_of_guests=5, booking_date=self.when
        )

        self.list_url = reverse("booking-list")

    def authenticate(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    # -- authentication ---------------------------------------------------- #
    def test_anonymous_cannot_list_bookings(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_anonymous_cannot_create_booking(self):
        response = self.client.post(
            self.list_url,
            {"name": "Ghost", "no_of_guests": 2, "booking_date": self.when.isoformat()},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Booking.objects.count(), 2)

    # -- scoping ----------------------------------------------------------- #
    def test_user_sees_only_their_own_bookings(self):
        self.authenticate(self.alice_token)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row["name"] for row in results_of(response)]
        self.assertEqual(names, ["Alice"])

    def test_user_cannot_retrieve_another_users_booking(self):
        self.authenticate(self.alice_token)
        response = self.client.get(reverse("booking-detail", args=[self.bob_booking.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_delete_another_users_booking(self):
        self.authenticate(self.alice_token)
        response = self.client.delete(reverse("booking-detail", args=[self.bob_booking.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Booking.objects.filter(id=self.bob_booking.id).exists())

    def test_staff_sees_every_booking(self):
        staff = User.objects.create_user(
            username="manager", password="CapstonePass123!", is_staff=True
        )
        self.authenticate(Token.objects.create(user=staff))
        response = self.client.get(self.list_url)
        self.assertEqual(len(results_of(response)), 2)

    # -- creation ---------------------------------------------------------- #
    def test_booking_is_stamped_with_the_authenticated_user(self):
        self.authenticate(self.alice_token)
        response = self.client.post(
            self.list_url,
            {"name": "Alice party", "no_of_guests": 6, "booking_date": self.when.isoformat()},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Booking.objects.get(name="Alice party").user, self.alice)

    def test_client_cannot_book_on_behalf_of_another_user(self):
        """A client-supplied ``user`` field is ignored -- the token decides the owner."""
        self.authenticate(self.alice_token)
        response = self.client.post(
            self.list_url,
            {
                "user": self.bob.id,
                "name": "Forged",
                "no_of_guests": 3,
                "booking_date": self.when.isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Booking.objects.get(name="Forged").user, self.alice)

    def test_owner_can_update_their_booking(self):
        self.authenticate(self.alice_token)
        response = self.client.patch(
            reverse("booking-detail", args=[self.alice_booking.id]), {"no_of_guests": 8}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.alice_booking.refresh_from_db()
        self.assertEqual(self.alice_booking.no_of_guests, 8)


class HtmlRouteTest(APITestCase):
    """The static/HTML side of the site renders."""

    def test_index_renders(self):
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Little Lemon")

    def test_menu_page_lists_items(self):
        Menu.objects.create(title="Greek Salad", price=Decimal("10.00"), inventory=12)
        response = self.client.get(reverse("menu"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Greek Salad")

    def test_booking_page_prompts_anonymous_visitors_to_log_in(self):
        response = self.client.get(reverse("book"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "log in")

    def test_login_and_register_pages_render(self):
        self.assertEqual(self.client.get(reverse("login")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("register")).status_code, status.HTTP_200_OK)

    def test_registration_creates_a_user(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newdiner",
                "password1": "CapstonePass123!",
                "password2": "CapstonePass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertTrue(User.objects.filter(username="newdiner").exists())
