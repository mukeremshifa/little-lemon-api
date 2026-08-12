"""Data model for the Little Lemon restaurant API."""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction


class Category(models.Model):
    """A menu section, e.g. "Starters", "Mains", "Desserts"."""

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=255, db_index=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class MenuItem(models.Model):
    """A single dish on the menu.

    ``featured`` doubles as the "item of the day" flag. Exactly one menu item may
    be featured at a time; :meth:`save` demotes any previous holder of the flag.
    """

    title = models.CharField(max_length=255, db_index=True)
    price = models.DecimalField(
        max_digits=6, decimal_places=2, db_index=True,
        validators=[MinValueValidator(0)],
    )
    featured = models.BooleanField(default=False, db_index=True)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="menu_items"
    )

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return f"{self.title} ({self.price})"

    @transaction.atomic
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.featured:
            # Enforce a single item of the day across the whole menu.
            MenuItem.objects.filter(featured=True).exclude(pk=self.pk).update(featured=False)


class Cart(models.Model):
    """A customer's pending line item. Cleared when the order is placed."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart_items"
    )
    menuitem = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1)]
    )
    # unit_price / price are denormalised so the cart survives later price changes.
    unit_price = models.DecimalField(max_digits=6, decimal_places=2)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        # One row per menu item per customer; quantity carries the count.
        constraints = [
            models.UniqueConstraint(fields=["user", "menuitem"], name="unique_cart_item")
        ]

    def __str__(self) -> str:
        return f"{self.user} x{self.quantity} {self.menuitem}"

    def save(self, *args, **kwargs):
        # Always derive money from the live menu price; never trust the client.
        self.unit_price = self.menuitem.price
        self.price = self.unit_price * self.quantity
        super().save(*args, **kwargs)


class Order(models.Model):
    """A placed order.

    ``status`` is False while the order is out for delivery and True once the
    delivery crew marks it delivered.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders"
    )
    delivery_crew = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="delivery_orders",
        null=True,
        blank=True,
    )
    status = models.BooleanField(default=False, db_index=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date = models.DateField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self) -> str:
        return f"Order #{self.pk} by {self.user}"

    @property
    def delivered(self) -> bool:
        """Readable alias for ``status``."""
        return self.status


class OrderItem(models.Model):
    """A frozen snapshot of one cart line at the moment the order was placed."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menuitem = models.ForeignKey(MenuItem, on_delete=models.PROTECT)
    quantity = models.PositiveSmallIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=6, decimal_places=2)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "menuitem"], name="unique_order_item")
        ]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.menuitem} on order #{self.order_id}"
