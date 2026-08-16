"""Views for the Little Lemon capstone project.

HTML routes::

    /                    home page
    /menu/               menu listing rendered from the database
    /book/               table booking form
    /accounts/register/  user registration

API endpoints (all prefixed with ``/api/``)::

    menu/                GET list | POST create
    menu/<pk>/           GET retrieve | PUT/PATCH/DELETE update/remove
    booking/tables/      GET list | POST create        (authentication required)
    booking/tables/<pk>/ GET | PUT/PATCH/DELETE        (authentication required)
"""
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import CreateView
from rest_framework import generics, viewsets
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly

from .models import Booking, Menu
from .serializers import BookingSerializer, MenuSerializer


# --------------------------------------------------------------------------- #
# HTML pages
# --------------------------------------------------------------------------- #
def index(request):
    """Restaurant home page."""
    return render(request, "index.html")


def menu(request):
    """Menu page, rendered from the Menu table."""
    return render(request, "menu.html", {"menu_items": Menu.objects.all()})


def book(request):
    """Table booking page. The form posts to the API via fetch()."""
    return render(request, "book.html")


class RegisterView(CreateView):
    """Browser-facing user registration, on top of Django's built-in form."""

    form_class = UserCreationForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("login")


# --------------------------------------------------------------------------- #
# Menu API
# --------------------------------------------------------------------------- #
class MenuItemsView(generics.ListCreateAPIView):
    """Browse the menu (open to all); create items (authenticated only)."""

    queryset = Menu.objects.all()
    serializer_class = MenuSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class SingleMenuItemView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve a single item (open); update or delete it (authenticated only)."""

    queryset = Menu.objects.all()
    serializer_class = MenuSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


# --------------------------------------------------------------------------- #
# Table booking API  -- authentication required on every action
# --------------------------------------------------------------------------- #
class BookingViewSet(viewsets.ModelViewSet):
    """Full CRUD over table reservations, restricted to authenticated users."""

    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Customers see only their own reservations; staff see all of them.

        Scoping the queryset (rather than checking object permissions) means a
        request for someone else's booking returns 404 instead of 403 -- the API
        never confirms that another customer's reservation exists.
        """
        bookings = Booking.objects.all()
        if self.request.user.is_staff:
            return bookings
        return bookings.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Stamp the reservation with the authenticated caller."""
        serializer.save(user=self.request.user)
