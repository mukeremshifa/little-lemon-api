"""End-to-end tests — one test per acceptance criterion in guide.md.

Run with::

    python manage.py test
"""
from decimal import Decimal

from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Cart, Category, MenuItem, Order, OrderItem
from .permissions import DELIVERY_CREW_GROUP, MANAGER_GROUP

User = get_user_model()

PASSWORD = "SuperSecret123!"

# Rate limits protect production, not the test suite; a fast hasher keeps the
# many token logins below from dominating the run time.
TEST_REST_FRAMEWORK = {
    **django_settings.REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {"anon": None, "user": None},
}


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    REST_FRAMEWORK=TEST_REST_FRAMEWORK,
)
class LittleLemonAPITests(APITestCase):
    """Every criterion is asserted through the HTTP API, as a real client would."""

    def setUp(self):
        self.manager_group = Group.objects.create(name=MANAGER_GROUP)
        self.crew_group = Group.objects.create(name=DELIVERY_CREW_GROUP)

        self.admin = User.objects.create_superuser("admin", "admin@ll.test", PASSWORD)
        self.manager = User.objects.create_user("manager", "manager@ll.test", PASSWORD)
        self.manager.groups.add(self.manager_group)
        self.crew = User.objects.create_user("crew", "crew@ll.test", PASSWORD)
        self.crew.groups.add(self.crew_group)
        self.customer = User.objects.create_user("customer", "customer@ll.test", PASSWORD)
        self.other_customer = User.objects.create_user("other", "other@ll.test", PASSWORD)

        self.starters = Category.objects.create(slug="starters", title="Starters")
        self.desserts = Category.objects.create(slug="desserts", title="Desserts")
        self.salad = MenuItem.objects.create(
            title="Greek Salad", price=Decimal("8.99"), category=self.starters
        )
        self.baklava = MenuItem.objects.create(
            title="Baklava", price=Decimal("4.50"), category=self.desserts
        )

    # -- helpers ----------------------------------------------------------- #
    def auth(self, user):
        """Authenticate the shared client as ``user`` using a real auth token."""
        response = self.client.post(
            "/api/token/login/", {"username": user.username, "password": PASSWORD}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        token = response.data["auth_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        return token

    def place_order_for(self, user):
        """Fill a cart and check out, returning the created order."""
        self.auth(user)
        self.client.post("/api/cart/menu-items/", {"menuitem": self.salad.id, "quantity": 2})
        response = self.client.post("/api/orders/")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return Order.objects.get(pk=response.data["id"])

    # -- 1 ----------------------------------------------------------------- #
    def test_01_admin_can_assign_users_to_manager_group(self):
        self.auth(self.admin)
        response = self.client.post(
            "/api/groups/manager/users/", {"username": self.customer.username}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(self.customer.groups.filter(name=MANAGER_GROUP).exists())

    # -- 2 ----------------------------------------------------------------- #
    def test_02_manager_group_readable_with_admin_token_only(self):
        self.auth(self.admin)
        response = self.client.get("/api/groups/manager/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("manager", [u["username"] for u in response.data])

        # A customer token must not reach the group endpoint.
        self.auth(self.customer)
        self.assertEqual(
            self.client.get("/api/groups/manager/users/").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    # -- 3 ----------------------------------------------------------------- #
    def test_03_admin_can_add_menu_items(self):
        self.auth(self.admin)
        response = self.client.post(
            "/api/menu-items/",
            {"title": "Lemon Chicken", "price": "15.00", "category_id": self.starters.id},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(MenuItem.objects.filter(title="Lemon Chicken").exists())

        # A customer may not add menu items.
        self.auth(self.customer)
        forbidden = self.client.post(
            "/api/menu-items/",
            {"title": "Free Lunch", "price": "0.01", "category_id": self.starters.id},
        )
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

    # -- 4 ----------------------------------------------------------------- #
    def test_04_admin_can_add_categories(self):
        self.auth(self.admin)
        response = self.client.post("/api/categories/", {"slug": "drinks", "title": "Drinks"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(Category.objects.filter(slug="drinks").exists())

    # -- 5 ----------------------------------------------------------------- #
    def test_05_managers_can_log_in(self):
        response = self.client.post(
            "/api/token/login/", {"username": "manager", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("auth_token", response.data)

    # -- 6 ----------------------------------------------------------------- #
    def test_06_manager_can_update_item_of_the_day(self):
        self.salad.featured = True
        self.salad.save()

        self.auth(self.manager)
        response = self.client.put(
            "/api/menu-items/item-of-the-day/", {"menuitem": self.baklava.id}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        self.baklava.refresh_from_db()
        self.salad.refresh_from_db()
        self.assertTrue(self.baklava.featured)
        self.assertFalse(self.salad.featured, "the previous item of the day must be demoted")

        # It is readable by anyone signed in.
        self.auth(self.customer)
        current = self.client.get("/api/menu-items/item-of-the-day/")
        self.assertEqual(current.data["title"], "Baklava")

        # ...and a customer cannot change it.
        self.assertEqual(
            self.client.put(
                "/api/menu-items/item-of-the-day/", {"menuitem": self.salad.id}
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_06b_manager_can_patch_featured_but_not_price(self):
        self.auth(self.manager)
        ok = self.client.patch(f"/api/menu-items/{self.salad.id}/", {"featured": True})
        self.assertEqual(ok.status_code, status.HTTP_200_OK, ok.data)

        denied = self.client.patch(f"/api/menu-items/{self.salad.id}/", {"price": "0.10"})
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    # -- 7 ----------------------------------------------------------------- #
    def test_07_manager_can_assign_users_to_delivery_crew(self):
        self.auth(self.manager)
        response = self.client.post(
            "/api/groups/delivery-crew/users/", {"username": self.other_customer.username}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(self.other_customer.groups.filter(name=DELIVERY_CREW_GROUP).exists())

        # And can take them off the crew again.
        removed = self.client.delete(
            f"/api/groups/delivery-crew/users/{self.other_customer.id}/"
        )
        self.assertEqual(removed.status_code, status.HTTP_200_OK)
        self.assertFalse(self.other_customer.groups.filter(name=DELIVERY_CREW_GROUP).exists())

    # -- 8 ----------------------------------------------------------------- #
    def test_08_manager_can_assign_orders_to_delivery_crew(self):
        order = self.place_order_for(self.customer)

        self.auth(self.manager)
        response = self.client.patch(
            f"/api/orders/{order.id}/", {"delivery_crew": self.crew.id}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        order.refresh_from_db()
        self.assertEqual(order.delivery_crew, self.crew)

    # -- 9 ----------------------------------------------------------------- #
    def test_09_delivery_crew_sees_only_assigned_orders(self):
        assigned = self.place_order_for(self.customer)
        unassigned = self.place_order_for(self.other_customer)
        assigned.delivery_crew = self.crew
        assigned.save()

        self.auth(self.crew)
        response = self.client.get("/api/orders/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [o["id"] for o in response.data["results"]]
        self.assertEqual(ids, [assigned.id])
        self.assertNotIn(unassigned.id, ids)

        # Direct access to an unassigned order is a 404, not a leak.
        self.assertEqual(
            self.client.get(f"/api/orders/{unassigned.id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    # -- 10 ---------------------------------------------------------------- #
    def test_10_delivery_crew_can_mark_order_delivered(self):
        order = self.place_order_for(self.customer)
        order.delivery_crew = self.crew
        order.save()

        self.auth(self.crew)
        response = self.client.patch(f"/api/orders/{order.id}/", {"status": True})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        order.refresh_from_db()
        self.assertTrue(order.status)

        # The crew may not reassign the order to somebody else.
        denied = self.client.patch(f"/api/orders/{order.id}/", {"delivery_crew": self.crew.id})
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)

    # -- 11 ---------------------------------------------------------------- #
    def test_11_customers_can_register(self):
        response = self.client.post(
            "/api/users/",
            {"username": "newbie", "email": "newbie@ll.test", "password": PASSWORD},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(User.objects.filter(username="newbie").exists())

    # -- 12 ---------------------------------------------------------------- #
    def test_12_customers_can_log_in_and_get_a_token(self):
        response = self.client.post(
            "/api/token/login/", {"username": "customer", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data["auth_token"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        me = self.client.get("/api/users/me/")
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data["username"], "customer")

    # -- 13 ---------------------------------------------------------------- #
    def test_13_customers_can_browse_categories(self):
        self.auth(self.customer)
        response = self.client.get("/api/categories/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [c["title"] for c in response.data["results"]]
        self.assertCountEqual(titles, ["Starters", "Desserts"])

    # -- 14 ---------------------------------------------------------------- #
    def test_14_customers_can_browse_all_menu_items(self):
        self.auth(self.customer)
        response = self.client.get("/api/menu-items/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    # -- 15 ---------------------------------------------------------------- #
    def test_15_customers_can_browse_menu_items_by_category(self):
        self.auth(self.customer)
        for query in ("desserts", "Desserts", str(self.desserts.id)):
            with self.subTest(query=query):
                response = self.client.get(f"/api/menu-items/?category={query}")
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                titles = [i["title"] for i in response.data["results"]]
                self.assertEqual(titles, ["Baklava"])

    # -- 16 ---------------------------------------------------------------- #
    def test_16_customers_can_paginate_menu_items(self):
        MenuItem.objects.create(title="Falafel", price=Decimal("12.25"), category=self.starters)
        self.auth(self.customer)

        page1 = self.client.get("/api/menu-items/?perpage=2&page=1")
        page2 = self.client.get("/api/menu-items/?perpage=2&page=2")
        self.assertEqual(page1.data["count"], 3)
        self.assertEqual(len(page1.data["results"]), 2)
        self.assertEqual(len(page2.data["results"]), 1)
        self.assertIsNotNone(page1.data["next"])

    # -- 17 ---------------------------------------------------------------- #
    def test_17_customers_can_sort_menu_items_by_price(self):
        self.auth(self.customer)
        ascending = self.client.get("/api/menu-items/?ordering=price")
        descending = self.client.get("/api/menu-items/?ordering=-price")

        self.assertEqual(
            [i["title"] for i in ascending.data["results"]], ["Baklava", "Greek Salad"]
        )
        self.assertEqual(
            [i["title"] for i in descending.data["results"]], ["Greek Salad", "Baklava"]
        )

    # -- 18 ---------------------------------------------------------------- #
    def test_18_customers_can_add_menu_items_to_the_cart(self):
        self.auth(self.customer)
        response = self.client.post(
            "/api/cart/menu-items/", {"menuitem": self.salad.id, "quantity": 3}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        line = Cart.objects.get(user=self.customer, menuitem=self.salad)
        self.assertEqual(line.quantity, 3)
        # Prices are computed server-side from the live menu price.
        self.assertEqual(line.unit_price, Decimal("8.99"))
        self.assertEqual(line.price, Decimal("26.97"))

    # -- 19 ---------------------------------------------------------------- #
    def test_19_customers_can_read_back_their_cart(self):
        self.auth(self.customer)
        self.client.post("/api/cart/menu-items/", {"menuitem": self.salad.id, "quantity": 1})

        response = self.client.get("/api/cart/menu-items/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["menuitem_detail"]["title"], "Greek Salad")

        # One customer never sees another's cart.
        self.auth(self.other_customer)
        self.assertEqual(len(self.client.get("/api/cart/menu-items/").data), 0)

    # -- 20 ---------------------------------------------------------------- #
    def test_20_customers_can_place_orders(self):
        self.auth(self.customer)
        self.client.post("/api/cart/menu-items/", {"menuitem": self.salad.id, "quantity": 2})
        self.client.post("/api/cart/menu-items/", {"menuitem": self.baklava.id, "quantity": 1})

        response = self.client.post("/api/orders/")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Decimal(response.data["total"]), Decimal("22.48"))
        self.assertEqual(len(response.data["items"]), 2)

        order = Order.objects.get(pk=response.data["id"])
        self.assertEqual(OrderItem.objects.filter(order=order).count(), 2)
        # Checkout empties the cart.
        self.assertEqual(Cart.objects.filter(user=self.customer).count(), 0)

        # An empty cart cannot be checked out.
        self.assertEqual(
            self.client.post("/api/orders/").status_code, status.HTTP_400_BAD_REQUEST
        )

    # -- 21 ---------------------------------------------------------------- #
    def test_21_customers_browse_only_their_own_orders(self):
        mine = self.place_order_for(self.customer)
        theirs = self.place_order_for(self.other_customer)

        self.auth(self.customer)
        response = self.client.get("/api/orders/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [o["id"] for o in response.data["results"]]
        self.assertEqual(ids, [mine.id])

        self.assertEqual(
            self.client.get(f"/api/orders/{theirs.id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        # Customers cannot self-assign a delivery crew or mark orders delivered.
        self.assertEqual(
            self.client.patch(f"/api/orders/{mine.id}/", {"status": True}).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    # -- cross-cutting ------------------------------------------------------ #
    def test_22_anonymous_access_is_rejected(self):
        for url in ("/api/menu-items/", "/api/categories/", "/api/cart/menu-items/", "/api/orders/"):
            with self.subTest(url=url):
                self.assertEqual(
                    self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED
                )

    def test_23_manager_sees_every_order(self):
        self.place_order_for(self.customer)
        self.place_order_for(self.other_customer)

        self.auth(self.manager)
        response = self.client.get("/api/orders/")
        self.assertEqual(response.data["count"], 2)
