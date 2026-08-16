"""URL routes for the Little Lemon API app (mounted under /api/)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"tables", views.BookingViewSet, basename="booking")

urlpatterns = [
    path("menu/", views.MenuItemsView.as_view(), name="menu-items"),
    path("menu/<int:pk>/", views.SingleMenuItemView.as_view(), name="menu-item-detail"),
    path("booking/", include(router.urls)),
]
