"""Create the role groups and a demo dataset.

    python manage.py seed_demo

Idempotent: re-running it updates rather than duplicates.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

from LittleLemonAPI.models import Category, MenuItem
from LittleLemonAPI.permissions import DELIVERY_CREW_GROUP, MANAGER_GROUP

User = get_user_model()

DEMO_PASSWORD = "LittleLemon123!"

CATEGORIES = [
    ("starters", "Starters"),
    ("mains", "Mains"),
    ("desserts", "Desserts"),
    ("drinks", "Drinks"),
]

MENU = [
    ("Hummus and Pita", "6.50", "starters"),
    ("Greek Salad", "8.99", "starters"),
    ("Grilled Fish", "18.75", "mains"),
    ("Lemon Chicken", "15.00", "mains"),
    ("Falafel Plate", "12.25", "mains"),
    ("Lemon Dessert", "5.75", "desserts"),
    ("Baklava", "4.50", "desserts"),
    ("Mint Lemonade", "3.25", "drinks"),
]


class Command(BaseCommand):
    help = "Seed role groups, demo users, categories and menu items."

    @transaction.atomic
    def handle(self, *args, **options):
        manager_group, _ = Group.objects.get_or_create(name=MANAGER_GROUP)
        crew_group, _ = Group.objects.get_or_create(name=DELIVERY_CREW_GROUP)

        admin, created = User.objects.get_or_create(
            username="admin", defaults={"email": "admin@littlelemon.test"}
        )
        admin.is_staff = True
        admin.is_superuser = True
        admin.set_password(DEMO_PASSWORD)
        admin.save()

        for username, group in (("manager", manager_group), ("crew", crew_group), ("customer", None)):
            user, _ = User.objects.get_or_create(
                username=username, defaults={"email": f"{username}@littlelemon.test"}
            )
            user.set_password(DEMO_PASSWORD)
            user.save()
            if group:
                user.groups.add(group)

        categories = {}
        for slug, title in CATEGORIES:
            categories[slug], _ = Category.objects.get_or_create(
                slug=slug, defaults={"title": title}
            )

        for title, price, cat_slug in MENU:
            MenuItem.objects.update_or_create(
                title=title,
                defaults={"price": Decimal(price), "category": categories[cat_slug]},
            )

        # Promote one dish as the item of the day.
        item = MenuItem.objects.get(title="Lemon Dessert")
        item.featured = True
        item.save()

        self.stdout.write(self.style.SUCCESS(
            "Seeded groups, users (admin / manager / crew / customer, password "
            f"'{DEMO_PASSWORD}'), {len(CATEGORIES)} categories and {len(MENU)} menu items."
        ))
