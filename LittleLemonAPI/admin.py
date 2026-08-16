"""Django admin registration."""
from django.contrib import admin

from .models import Booking, Menu


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ("title", "price", "inventory")
    list_editable = ("price", "inventory")
    search_fields = ("title",)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("name", "no_of_guests", "booking_date", "user")
    list_filter = ("booking_date",)
    search_fields = ("name",)
