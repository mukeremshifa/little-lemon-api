"""URL routes for the Little Lemon API app (mounted under /api/)."""
from django.urls import path

from . import views

urlpatterns = [
    # Categories
    path("categories/", views.CategoriesView.as_view(), name="categories"),
    path("categories/<int:pk>/", views.SingleCategoryView.as_view(), name="category-detail"),

    # Menu items — item-of-the-day must precede the <int:pk> route.
    path("menu-items/", views.MenuItemsView.as_view(), name="menu-items"),
    path("menu-items/item-of-the-day/", views.ItemOfTheDayView.as_view(), name="item-of-the-day"),
    path("menu-items/<int:pk>/", views.SingleMenuItemView.as_view(), name="menu-item-detail"),

    # Role groups
    path("groups/manager/users/", views.ManagerUsersView.as_view(), name="manager-users"),
    path("groups/manager/users/<int:pk>/", views.SingleManagerUserView.as_view(), name="manager-user-detail"),
    path("groups/delivery-crew/users/", views.DeliveryCrewUsersView.as_view(), name="delivery-crew-users"),
    path("groups/delivery-crew/users/<int:pk>/", views.SingleDeliveryCrewUserView.as_view(), name="delivery-crew-user-detail"),

    # Cart
    path("cart/menu-items/", views.CartView.as_view(), name="cart"),

    # Orders
    path("orders/", views.OrdersView.as_view(), name="orders"),
    path("orders/<int:pk>/", views.SingleOrderView.as_view(), name="order-detail"),

    # Helper
    path("whoami/", views.whoami, name="whoami"),
]
